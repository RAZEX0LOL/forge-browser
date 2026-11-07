// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. https://mozilla.org/MPL/2.0/
package main

import (
	"archive/zip"
	"bytes"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net/url"
	"path"
	"strings"
	"time"
)

const publicKey = "MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAxTcplNZKRu82IwDG4cVdeah2JnTXdfMaTEwGlLRM1xlqqAmVvPITqVl0SwGtEoXE7QImpVoDFxNQsgD+MOnfDgLftJTVfpX9jORUGGDnUyXxsz2r5soQ/YglN4Krp0PZQdc5nPgAlmv2jx8fmmB2Pggjm4QkyvIHke3ZILdobY6IKpyumbPSuHk1d0BZUqKN9bDKZ60nWWR5ox4PmzfvrYl0+q54xzvs7AF9W80E7i9MnTgT0jpnt8nQwytQqU93JskiL6kPj4UBBCbM/1GR8pGuo1Wdc1/LyVKX4yJmETVYX9fafBZy49xboPgFvlAeBvo43GhyO7qtUnFNvEymlUJNxJi3XBEeID8ZXBFFOoh2p4/LgVkaTEQAnZlB/V+OQukxgWempaO5noJ7K41HRoyWXIOGrK0SfGGNDMDfQ20Cs48KJdUgyHOtSh6XdtAI9rCUfqWQydONB7+/TCqZa6xy6c1RcR4UiLXU4UIe7ye+DeAPOXkg1QvqS9PdYXE3AgMBAAE="
const maximumPackageBytes int64 = 600 * 1024 * 1024
const maximumExtractedBytes uint64 = 4 * 1024 * 1024 * 1024

type artifact struct {
	URL    string `json:"url"`
	SHA256 string `json:"sha256"`
	Bytes  int64  `json:"bytes"`
}

type desktopManifest struct {
	SchemaVersion int                 `json:"schemaVersion"`
	Channel       string              `json:"channel"`
	PackageName   string              `json:"packageName"`
	Sequence      int64               `json:"sequence"`
	Issued        int64               `json:"issued"`
	Expires       int64               `json:"expires"`
	BuildNumber   int64               `json:"buildNumber"`
	VersionName   string              `json:"versionName"`
	Artifacts     map[string]artifact `json:"artifacts"`
}

func packageURL(value string) bool {
	u, err := url.Parse(value)
	return err == nil && u.Scheme == "https" && u.Host == "razex.shop" && u.User == nil && u.RawQuery == "" &&
		u.Fragment == "" && u.RawPath == "" && strings.HasPrefix(u.Path, "/forge/downloads/Forge-development-") &&
		strings.HasSuffix(u.Path, ".zip") && path.Clean(u.Path) == u.Path && strings.Count(u.Path, "/") == 3 &&
		!strings.ContainsAny(u.Path, "\\\r\n\t ") && !u.ForceQuery
}

func verifyManifest(envelope []byte, now time.Time, minimumSequence int64, target string, keyDER []byte) (desktopManifest, artifact, error) {
	var empty desktopManifest
	var none artifact
	if len(envelope) > 65536 {
		return empty, none, errors.New("manifest exceeds limit")
	}
	var signed struct {
		Payload   string `json:"payload"`
		Signature string `json:"signature"`
	}
	decoder := json.NewDecoder(bytes.NewReader(envelope))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&signed); err != nil {
		return empty, none, err
	}
	if decoder.Decode(new(any)) != io.EOF {
		return empty, none, errors.New("trailing envelope data")
	}
	payload, err := base64.StdEncoding.DecodeString(signed.Payload)
	if err != nil {
		return empty, none, err
	}
	signature, err := base64.StdEncoding.DecodeString(signed.Signature)
	if err != nil {
		return empty, none, err
	}
	parsed, err := x509.ParsePKIXPublicKey(keyDER)
	if err != nil {
		return empty, none, err
	}
	key, ok := parsed.(*rsa.PublicKey)
	if !ok || key.N.BitLen() < 2048 {
		return empty, none, errors.New("invalid release verification key")
	}
	digest := sha256.Sum256(payload)
	if err := rsa.VerifyPKCS1v15(key, crypto.SHA256, digest[:], signature); err != nil {
		return empty, none, errors.New("manifest signature mismatch")
	}
	var manifest desktopManifest
	if err := json.Unmarshal(payload, &manifest); err != nil {
		return empty, none, err
	}
	file, ok := manifest.Artifacts[target]
	decodedHash, hashErr := hex.DecodeString(file.SHA256)
	if manifest.SchemaVersion != 1 || manifest.Channel != "desktop-development" || manifest.PackageName != "org.forgebrowser.development" ||
		manifest.Sequence <= 0 || manifest.Sequence < minimumSequence || manifest.BuildNumber <= 0 ||
		manifest.Issued < 0 || manifest.Issued > now.Unix()+300 || manifest.Expires <= now.Unix() ||
		manifest.Expires <= manifest.Issued || manifest.Expires-manifest.Issued > 14*86400 ||
		!ok || file.Bytes <= 0 || file.Bytes > maximumPackageBytes || hashErr != nil || len(decodedHash) != 32 ||
		file.SHA256 != strings.ToLower(file.SHA256) || !packageURL(file.URL) ||
		len(manifest.VersionName) == 0 || len(manifest.VersionName) > 64 || strings.ContainsAny(manifest.VersionName, "\r\n\t\x00") {
		return empty, none, errors.New("expired, incompatible or invalid update metadata")
	}
	return manifest, file, nil
}

func verifiedCopy(destination io.Writer, source io.Reader, file artifact) error {
	if file.Bytes <= 0 || file.Bytes > maximumPackageBytes {
		return errors.New("invalid package length")
	}
	digest := sha256.New()
	count, err := io.Copy(io.MultiWriter(destination, digest), io.LimitReader(source, file.Bytes+1))
	if err != nil {
		return err
	}
	if count != file.Bytes || hex.EncodeToString(digest.Sum(nil)) != file.SHA256 {
		return errors.New("download size/hash mismatch")
	}
	return nil
}

// Validate every entry before invoking ditto, including framework symlink targets.
func validateMacZIP(filename string) error {
	archive, err := zip.OpenReader(filename)
	if err != nil {
		return err
	}
	defer archive.Close()
	var total uint64
	seen := make(map[string]bool)
	hasInfo := false
	for _, file := range archive.File {
		name := strings.TrimSuffix(file.Name, "/")
		if name == "" || path.Clean(name) != name || strings.HasPrefix(name, "/") ||
			strings.ContainsAny(name, "\\\x00\r\n") || seen[name] ||
			!(name == "Forge.app" || strings.HasPrefix(name, "Forge.app/") || name == "__MACOSX" || strings.HasPrefix(name, "__MACOSX/")) {
			return fmt.Errorf("unsafe ZIP entry")
		}
		seen[name] = true
		if file.UncompressedSize64 > maximumExtractedBytes-total {
			return errors.New("extracted package exceeds limit")
		}
		total += file.UncompressedSize64
		if file.Mode().IsRegular() || file.FileInfo().IsDir() {
			if name == "Forge.app/Contents/Info.plist" && file.Mode().IsRegular() {
				hasInfo = true
			}
			continue
		}
		if file.Mode()&fs.ModeSymlink == 0 || file.UncompressedSize64 > 4096 {
			return errors.New("special ZIP entry is not allowed")
		}
		stream, err := file.Open()
		if err != nil {
			return err
		}
		link, err := io.ReadAll(io.LimitReader(stream, 4097))
		stream.Close()
		resolved := path.Join(path.Dir(name), string(link))
		if err != nil || len(link) == 0 || len(link) > 4096 || path.IsAbs(string(link)) ||
			strings.ContainsAny(string(link), "\\\x00\r\n") || !strings.HasPrefix(resolved, "Forge.app/") ||
			!strings.HasPrefix(name, "Forge.app/") {
			return errors.New("unsafe symlink in ZIP")
		}
	}
	if !hasInfo {
		return errors.New("ZIP has no Forge.app bundle")
	}
	return nil
}
