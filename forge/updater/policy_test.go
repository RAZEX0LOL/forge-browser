package main

import (
	"archive/zip"
	"bytes"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
	"time"
)

func fixture(t *testing.T) (desktopManifest, *rsa.PrivateKey, []byte) {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		t.Fatal(err)
	}
	manifest := desktopManifest{SchemaVersion: 1, Channel: "desktop-development", PackageName: bundleID,
		Sequence: 5, Issued: 1800000000 - 30, Expires: 1800000000 + 3600, BuildNumber: 2026110702, VersionName: "dev.2",
		Artifacts: map[string]artifact{"macos-arm64": {URL: "https://razex.shop/forge/downloads/Forge-development-test.zip", SHA256: strings.Repeat("a", 64), Bytes: 10}}}
	return manifest, key, der
}

func signedFixture(t *testing.T, manifest desktopManifest, key *rsa.PrivateKey) []byte {
	t.Helper()
	payload, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(payload)
	signature, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	envelope, err := json.Marshal(map[string]string{"payload": base64.StdEncoding.EncodeToString(payload), "signature": base64.StdEncoding.EncodeToString(signature)})
	if err != nil {
		t.Fatal(err)
	}
	return envelope
}

func TestReleaseKeyMatchesAndroidPinnedKey(t *testing.T) {
	java, err := os.ReadFile("../mobile/android/app/src/main/java/org/forgebrowser/mobile/UpdatePolicy.java")
	if err != nil {
		t.Fatal(err)
	}
	match := regexp.MustCompile(`PUBLIC_KEY = "([^"]+)"`).FindSubmatch(java)
	if len(match) != 2 || string(match[1]) != publicKey {
		t.Fatal("release public keys diverged")
	}
	der, err := base64.StdEncoding.DecodeString(publicKey)
	if err != nil {
		t.Fatal(err)
	}
	key, err := x509.ParsePKIXPublicKey(der)
	if err != nil || key.(*rsa.PublicKey).N.BitLen() != 3072 {
		t.Fatal("invalid pinned RSA-3072 key")
	}
}

func TestPublishedDesktopEnvelopeMatchesReleaseKey(t *testing.T) {
	envelope, err := os.ReadFile("../site/updates/desktop-macos-arm64.json")
	if err != nil {
		t.Fatal(err)
	}
	var signed struct {
		Payload string `json:"payload"`
	}
	if err := json.Unmarshal(envelope, &signed); err != nil {
		t.Fatal(err)
	}
	payload, err := base64.StdEncoding.DecodeString(signed.Payload)
	if err != nil {
		t.Fatal(err)
	}
	var recorded desktopManifest
	if err := json.Unmarshal(payload, &recorded); err != nil {
		t.Fatal(err)
	}
	key, err := base64.StdEncoding.DecodeString(publicKey)
	if err != nil {
		t.Fatal(err)
	}
	// A reproducible historical signature vector; runtime expiry/future rejection
	// is tested separately and the real updater always uses time.Now().
	manifest, file, err := verifyManifest(envelope, time.Unix(recorded.Issued+1, 0), 0, "macos-arm64", key)
	if err != nil {
		t.Fatal(err)
	}
	if manifest.BuildNumber != 2026110802 || file.SHA256 != "c3560f04b0565584244638ed5cb328a264664e81286ccd2390c8cf49bc3c3045" {
		t.Fatal("unexpected published bootstrap")
	}
}

func TestSignedManifestAndTampering(t *testing.T) {
	manifest, key, der := fixture(t)
	envelope := signedFixture(t, manifest, key)
	got, file, err := verifyManifest(envelope, time.Unix(1800000000, 0), 5, "macos-arm64", der)
	if err != nil || got.BuildNumber != manifest.BuildNumber || file.Bytes != 10 {
		t.Fatalf("%+v %v", got, err)
	}
	var signed map[string]string
	json.Unmarshal(envelope, &signed)
	signed["payload"] = base64.StdEncoding.EncodeToString([]byte(`{"buildNumber":999999999999}`))
	tampered, _ := json.Marshal(signed)
	if _, _, err = verifyManifest(tampered, time.Unix(1800000000, 0), 0, "macos-arm64", der); err == nil {
		t.Fatal("tampered payload accepted")
	}
	if _, _, err = verifyManifest(append(envelope, []byte(" {}")...), time.Unix(1800000000, 0), 0, "macos-arm64", der); err == nil {
		t.Fatal("trailing JSON accepted")
	}
}

func TestRejectedManifestStates(t *testing.T) {
	mutations := map[string]func(*desktopManifest){
		"expired":  func(m *desktopManifest) { m.Expires = 1800000000 },
		"future":   func(m *desktopManifest) { m.Issued = 1800000301 },
		"lifetime": func(m *desktopManifest) { m.Expires = m.Issued + 14*86400 + 1 },
		"rollback": func(m *desktopManifest) { m.Sequence = 4 },
		"package":  func(m *desktopManifest) { m.PackageName = "other" },
		"channel":  func(m *desktopManifest) { m.Channel = "android-development" },
		"build":    func(m *desktopManifest) { m.BuildNumber = 0 },
		"target":   func(m *desktopManifest) { delete(m.Artifacts, "macos-arm64") },
		"URL": func(m *desktopManifest) {
			f := m.Artifacts["macos-arm64"]
			f.URL = "https://evil.test/update.zip"
			m.Artifacts["macos-arm64"] = f
		},
		"size": func(m *desktopManifest) {
			f := m.Artifacts["macos-arm64"]
			f.Bytes = maximumPackageBytes + 1
			m.Artifacts["macos-arm64"] = f
		},
		"hash": func(m *desktopManifest) {
			f := m.Artifacts["macos-arm64"]
			f.SHA256 = "none"
			m.Artifacts["macos-arm64"] = f
		},
	}
	for label, mutate := range mutations {
		t.Run(label, func(t *testing.T) {
			m, key, der := fixture(t)
			mutate(&m)
			if _, _, err := verifyManifest(signedFixture(t, m, key), time.Unix(1800000000, 0), 5, "macos-arm64", der); err == nil {
				t.Fatal("unsafe metadata accepted")
			}
		})
	}
}

func TestPackageURLScope(t *testing.T) {
	if !packageURL("https://razex.shop/forge/downloads/Forge-development-test.zip") {
		t.Fatal("valid URL rejected")
	}
	for _, value := range []string{"http://razex.shop/forge/downloads/Forge-development-test.zip", "https://razex.shop:443/forge/downloads/Forge-development-test.zip",
		"https://user@razex.shop/forge/downloads/Forge-development-test.zip", "https://razex.shop/forge/downloads/../Forge-development-test.zip",
		"https://razex.shop/forge/downloads/Forge-development-test.zip?q=1", "https://razex.shop/forge/downloads/Forge-development-test.zip#x",
		"https://razex.shop/forge/downloads/Forge-development-%2e%2e.zip", "https://razex.shop/forge/downloads/Forge-development-test.zip?"} {
		if packageURL(value) {
			t.Fatal("unsafe URL accepted", value)
		}
	}
}

func TestStreamIntegrity(t *testing.T) {
	data := []byte{0, 255, 1, 2}
	digest := sha256.Sum256(data)
	file := artifact{Bytes: int64(len(data)), SHA256: hex.EncodeToString(digest[:])}
	var output bytes.Buffer
	if err := verifiedCopy(&output, bytes.NewReader(data), file); err != nil || !bytes.Equal(data, output.Bytes()) {
		t.Fatal(err)
	}
	for _, input := range [][]byte{data[:2], append(append([]byte{}, data...), 3), {0, 0, 0, 0}} {
		if err := verifiedCopy(&bytes.Buffer{}, bytes.NewReader(input), file); err == nil {
			t.Fatal("bad stream accepted")
		}
	}
}

func zipFixture(t *testing.T, name, target string, mode fs.FileMode) string {
	t.Helper()
	filename := filepath.Join(t.TempDir(), "fixture.zip")
	file, err := os.Create(filename)
	if err != nil {
		t.Fatal(err)
	}
	archive := zip.NewWriter(file)
	entry, _ := archive.Create("Forge.app/Contents/Info.plist")
	entry.Write([]byte("fixture"))
	if name != "" {
		header := &zip.FileHeader{Name: name}
		header.SetMode(mode)
		entry, err = archive.CreateHeader(header)
		if err != nil {
			t.Fatal(err)
		}
		entry.Write([]byte(target))
	}
	if err := archive.Close(); err != nil {
		t.Fatal(err)
	}
	file.Close()
	return filename
}

func TestZIPTraversalAndSymlinks(t *testing.T) {
	if err := validateMacZIP(zipFixture(t, "Forge.app/Contents/Frameworks/Foo.framework/Foo", "Versions/Current/Foo", fs.ModeSymlink|0o777)); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"../outside", "/absolute", "Forge.app/../outside", "Forge.app/Contents/Info.plist", "other.app/Contents/file", "Forge.app/evil\nfile"} {
		if err := validateMacZIP(zipFixture(t, name, "data", 0o644)); err == nil {
			t.Fatal("unsafe ZIP entry", name)
		}
	}
	for _, target := range []string{"/etc/passwd", "../../../../outside", "../..\\outside"} {
		if err := validateMacZIP(zipFixture(t, "Forge.app/Contents/link", target, fs.ModeSymlink|0o777)); err == nil {
			t.Fatal("unsafe ZIP symlink", target)
		}
	}
}

func TestReplacementRetainsBackupAndRollsBackFailures(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(fmtBool(fail), func(t *testing.T) {
			root := t.TempDir()
			app := filepath.Join(root, "Forge.app")
			candidate := filepath.Join(root, "candidate")
			backup := filepath.Join(root, "backup")
			os.Mkdir(app, 0o700)
			os.Mkdir(candidate, 0o700)
			os.WriteFile(filepath.Join(app, "old"), []byte("old"), 0o600)
			os.WriteFile(filepath.Join(candidate, "new"), []byte("new"), 0o600)
			rename := func(from, to string) error {
				if fail && from == candidate {
					return errors.New("simulated rename failure")
				}
				return os.Rename(from, to)
			}
			err := replaceWithBackup(app, candidate, backup, rename, os.Lstat)
			if fail {
				if err == nil {
					t.Fatal("failure hidden")
				}
				if _, err := os.Stat(filepath.Join(app, "old")); err != nil {
					t.Fatal("old app not restored")
				}
			} else {
				if err != nil {
					t.Fatal(err)
				}
				if _, err := os.Stat(filepath.Join(backup, "old")); err != nil {
					t.Fatal("backup lost")
				}
				if _, err := os.Stat(filepath.Join(app, "new")); err != nil {
					t.Fatal("new app missing")
				}
			}
		})
	}
}

func fmtBool(value bool) string {
	if value {
		return "rollback"
	}
	return "success"
}

func TestExistingBackupIsNeverOverwritten(t *testing.T) {
	root := t.TempDir()
	app := filepath.Join(root, "app")
	candidate := filepath.Join(root, "candidate")
	backup := filepath.Join(root, "backup")
	for _, dir := range []string{app, candidate, backup} {
		os.Mkdir(dir, 0o700)
	}
	if err := replaceWithBackup(app, candidate, backup, os.Rename, os.Lstat); err == nil {
		t.Fatal("existing backup overwritten")
	}
}

func TestRunningBrowserPreventsReplacement(t *testing.T) {
	if runtime.GOOS != "darwin" {
		t.Skip("macOS-native process inspection acceptance only")
	}
	root, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	app := filepath.Join(root, "Forge.app")
	dir := filepath.Join(app, "Contents", "MacOS")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	binary := filepath.Join(dir, "owned-browser-fixture")
	source := filepath.Join(root, "fixture.c")
	if err := os.WriteFile(source, []byte("#include <unistd.h>\nint main(void) { sleep(30); return 0; }\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if output, err := exec.Command("/usr/bin/clang", "-mmacosx-version-min=13.0", source, "-o", binary).CombinedOutput(); err != nil {
		t.Fatalf("owned native fixture compile failed: %v: %s", err, output)
	}
	command := exec.Command(binary)
	if err := command.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { command.Process.Kill(); command.Wait() }()
	if err := noRunningBrowser(app); err == nil {
		t.Fatal("running browser was not detected")
	}
	other := filepath.Join(root, "another-app")
	if err := os.Mkdir(other, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := noRunningBrowser(other); err != nil {
		t.Fatalf("unrelated process incorrectly blocked replacement: %#v", err)
	}
}

func TestLocalizedHelperMessagesHaveEnglishTranslations(t *testing.T) {
	for original, translated := range english {
		if original == "" || translated == "" || regexp.MustCompile(`[А-Яа-яЁё]`).MatchString(translated) {
			t.Fatal("invalid translation", original)
		}
	}
	locale = "en"
	if tr("Отмена") != "Cancel" {
		t.Fatal("English consent label missing")
	}
	locale = "ru"
	if tr("Отмена") != "Отмена" {
		t.Fatal("Russian consent label changed")
	}
}
