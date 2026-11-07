// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. https://mozilla.org/MPL/2.0/
package main

import (
	"context"
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// Release tooling must advance this monotonic build number for each new full package.
var currentBuild = "2026110701"

const teamID = "22YK6BV6UY"
const bundleID = "org.forgebrowser.development"

func main() {
	if len(os.Args) == 2 && os.Args[1] == "--version" {
		fmt.Printf("Forge full-package updater %s (%s/%s)\n", currentBuild, runtime.GOOS, runtime.GOARCH)
		return
	}
	validArguments := len(os.Args) == 1
	if len(os.Args) == 2 && (os.Args[1] == "--locale=en" || os.Args[1] == "--locale=ru") {
		locale = strings.TrimPrefix(os.Args[1], "--locale=")
		validArguments = true
	}
	if runtime.GOOS != "darwin" || !validArguments {
		fmt.Fprintln(os.Stderr, "Only the packaged macOS updater is enabled; no unattended install mode exists.")
		os.Exit(1)
	}
	if err := run(); err != nil {
		// Do not log network URLs or user paths to a public report.
		_ = notice(tr("Обновление не установлено. Проверь подключение, часы и права на папку приложения. Профиль не изменён. ") + tr(err.Error()))
		os.Exit(1)
	}
}

func dialog(message string, confirm bool) (bool, error) {
	message = tr(message)
	script := `on run argv
display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "Forge updates"
end run`
	if confirm {
		script = `on run argv
display dialog (item 1 of argv) buttons {"Отмена", "Продолжить"} default button "Отмена" cancel button "Отмена" with title "Forge updates"
end run`
	}
	script = strings.ReplaceAll(strings.ReplaceAll(script, "Отмена", tr("Отмена")), "Продолжить", tr("Продолжить"))
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()
	_, err := exec.CommandContext(ctx, "/usr/bin/osascript", "-e", script, message).Output()
	if err != nil && confirm {
		return false, nil // Closing/cancelling never means consent.
	}
	return err == nil, err
}

func notice(message string) error { _, err := dialog(message, false); return err }

func rejectSymlinks(name string) error {
	name = filepath.Clean(name)
	for {
		info, err := os.Lstat(name)
		if err != nil || info.Mode()&os.ModeSymlink != 0 {
			return errors.New("Путь приложения или служебной папки недоступен/содержит симлинк.")
		}
		next := filepath.Dir(name)
		if next == name {
			return nil
		}
		name = next
	}
}

func appPath() (string, error) {
	executable, err := os.Executable()
	if err != nil {
		return "", err
	}
	if filepath.Base(executable) != "forge-update" || filepath.Base(filepath.Dir(executable)) != "MacOS" ||
		filepath.Base(filepath.Dir(filepath.Dir(executable))) != "Contents" {
		return "", errors.New("Запускай updater только из установленного Forge.app.")
	}
	app := filepath.Dir(filepath.Dir(filepath.Dir(executable)))
	if filepath.Base(app) != "Forge.app" {
		return "", errors.New("Ожидается Forge.app.")
	}
	return app, rejectSymlinks(executable)
}

func httpClient() *http.Client {
	return &http.Client{Transport: &http.Transport{Proxy: http.ProxyFromEnvironment, DisableCompression: true,
		TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}, TLSHandshakeTimeout: 15 * time.Second,
		ResponseHeaderTimeout: 30 * time.Second, IdleConnTimeout: 30 * time.Second},
		CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("Redirects are not allowed") }}
}

func response(ctx context.Context, client *http.Client, url string, maximum int64) (*http.Response, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("User-Agent", "Forge-Desktop-Update/1")
	request.Header.Set("Accept-Encoding", "identity")
	result, err := client.Do(request)
	if err != nil {
		return nil, errors.New("Ошибка HTTPS-запроса обновления.")
	}
	encoding := result.Header.Get("Content-Encoding")
	if result.StatusCode != 200 || result.ContentLength > maximum || (encoding != "" && encoding != "identity") {
		result.Body.Close()
		return nil, errors.New("Неподходящий ответ сервера обновлений.")
	}
	return result, nil
}

func run() error {
	app, err := appPath()
	if err != nil {
		return err
	}
	if err := assessMacApp(app); err != nil {
		return err
	}
	consent, err := dialog("Проверить подписанное обновление на razex.shop? Сервер получит IP-адрес и запрос updater, но не историю, вкладки или cookies. Проверка только вручную. Это development-канал без гарантии своевременных исправлений безопасности.", true)
	if err != nil || !consent {
		return err
	}
	config, err := os.UserConfigDir()
	if err != nil {
		return err
	}
	stateDir := filepath.Join(config, "ForgeUpdates")
	if err := os.MkdirAll(stateDir, 0o700); err != nil {
		return err
	}
	if err := rejectSymlinks(stateDir); err != nil {
		return err
	}
	lock, err := os.OpenFile(filepath.Join(stateDir, "update.lock"), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return errors.New("Updater уже запущен либо остался lock после сбоя. Не запускай второй экземпляр.")
	}
	lock.Close()
	defer os.Remove(filepath.Join(stateDir, "update.lock"))
	stateFile := filepath.Join(stateDir, "macos-"+runtime.GOARCH+".json")
	var state struct {
		Sequence int64 `json:"sequence"`
	}
	if bytes, err := os.ReadFile(stateFile); err == nil {
		if err := rejectSymlinks(stateFile); err != nil {
			return err
		}
		if json.Unmarshal(bytes, &state) != nil || state.Sequence < 0 {
			return errors.New("Некорректное состояние защиты от отката.")
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	target := "macos-arm64"
	if runtime.GOARCH == "amd64" {
		target = "macos-intel"
	} else if runtime.GOARCH != "arm64" {
		return errors.New("Неподдерживаемая архитектура.")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	client := httpClient()
	result, err := response(ctx, client, "https://razex.shop/forge/updates/desktop-"+target+".json", 65536)
	if err != nil {
		cancel()
		return err
	}
	envelope, err := io.ReadAll(io.LimitReader(result.Body, 65537))
	result.Body.Close()
	cancel()
	if err != nil {
		return err
	}
	key, err := base64.StdEncoding.DecodeString(publicKey)
	if err != nil {
		return err
	}
	manifest, file, err := verifyManifest(envelope, time.Now(), state.Sequence, target, key)
	if err != nil {
		return errors.New("Подпись, срок или параметры манифеста не прошли проверку.")
	}
	state.Sequence = manifest.Sequence
	encoded, _ := json.Marshal(state)
	temporaryState, err := os.CreateTemp(stateDir, ".sequence-")
	if err != nil {
		return err
	}
	defer os.Remove(temporaryState.Name())
	if _, err = temporaryState.Write(encoded); err != nil {
		temporaryState.Close()
		return err
	}
	if err = temporaryState.Sync(); err != nil {
		temporaryState.Close()
		return err
	}
	if err = temporaryState.Close(); err != nil {
		return err
	}
	if err = os.Rename(temporaryState.Name(), stateFile); err != nil {
		return err
	}
	build, err := strconv.ParseInt(currentBuild, 10, 64)
	if err != nil {
		return err
	}
	if manifest.BuildNumber <= build {
		return notice("Более нового совместимого пакета Forge нет.")
	}
	consent, err = dialog(fmt.Sprintf(tr("Доступен Forge %s (%d МиБ). Скачать полный пакет? Потребуется закрыть браузер и отдельно подтвердить замену приложения. Прежнее приложение останется рядом для отката; профиль не изменяется."), manifest.VersionName, file.Bytes/1048576), true)
	if err != nil || !consent {
		return err
	}
	// Stage on the destination filesystem before moving the old app; never elevate or overwrite another path.
	stage, err := os.MkdirTemp(filepath.Dir(app), ".Forge-update-")
	if err != nil {
		return errors.New("Нет прав на папку приложения. Установи пакет вручную; updater не запрашивает root.")
	}
	defer os.RemoveAll(stage)
	filename := filepath.Join(stage, "package.zip")
	ctx, cancel = context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	result, err = response(ctx, client, file.URL, file.Bytes)
	if err != nil {
		return err
	}
	archive, err := os.OpenFile(filename, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		result.Body.Close()
		return err
	}
	err = verifiedCopy(archive, result.Body, file)
	result.Body.Close()
	if syncErr := archive.Sync(); err == nil {
		err = syncErr
	}
	if closeErr := archive.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	if manifest.Expires <= time.Now().Unix() {
		return errors.New("Манифест истёк во время скачивания.")
	}
	if err := validateMacZIP(filename); err != nil {
		return err
	}
	extracted := filepath.Join(stage, "unpacked")
	if err := command(3*time.Minute, "/usr/bin/ditto", "-x", "-k", filename, extracted); err != nil {
		return err
	}
	newApp := filepath.Join(extracted, "Forge.app")
	if err := assessMacApp(newApp); err != nil {
		return err
	}
	newHelper := filepath.Join(newApp, "Contents", "MacOS", "forge-update")
	if err := rejectSymlinks(newHelper); err != nil {
		return err
	}
	versionCtx, versionCancel := context.WithTimeout(context.Background(), 15*time.Second)
	versionOutput, versionErr := exec.CommandContext(versionCtx, newHelper, "--version").Output()
	versionCancel()
	expectedVersion := fmt.Sprintf("Forge full-package updater %d (darwin/%s)", manifest.BuildNumber, runtime.GOARCH)
	if versionErr != nil || strings.TrimSpace(string(versionOutput)) != expectedVersion {
		return errors.New("Updater build/architecture does not match signed package metadata.")
	}
	// Ensure Gatekeeper also sees an internet-origin application on its next launch; never clear quarantine.
	if err := command(30*time.Second, "/usr/bin/xattr", "-w", "com.apple.quarantine", fmt.Sprintf("0083;%x;Forge;", time.Now().Unix()), newApp); err != nil {
		return err
	}
	consent, err = dialog("Пакет проверен: SHA-256, размер, Developer ID, идентификатор приложения и Gatekeeper. Закрой все окна Forge, затем нажми «Продолжить» для замены. Ничего не будет установлено, пока браузер работает.", true)
	if err != nil || !consent {
		return err
	}
	if err := noRunningBrowser(app); err != nil {
		return err
	}
	if err := rejectSymlinks(app); err != nil {
		return err
	}
	if err := assessMacApp(app); err != nil {
		return err
	}
	backup := app + ".backup-" + currentBuild + "-" + time.Now().UTC().Format("20060102T150405Z")
	if err := replaceWithBackup(app, newApp, backup, os.Rename, os.Lstat); err != nil {
		return err
	}
	return notice("Forge обновлён. Запусти Forge.app обычным способом. Прежнее приложение сохранено рядом как .backup; профиль остался на месте.")
}

func command(timeout time.Duration, name string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	if err := exec.CommandContext(ctx, name, args...).Run(); err != nil {
		return errors.New("Системная проверка/операция пакета отклонена.")
	}
	return nil
}

func assessMacApp(app string) error {
	if err := rejectSymlinks(app); err != nil {
		return err
	}
	if err := command(2*time.Minute, "/usr/bin/codesign", "--verify", "--deep", "--strict", app); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	output, err := exec.CommandContext(ctx, "/usr/bin/codesign", "-d", "--verbose=4", app).CombinedOutput()
	if err != nil || !strings.Contains("\n"+string(output), "\nTeamIdentifier="+teamID+"\n") ||
		!strings.Contains("\n"+string(output), "\nIdentifier="+bundleID+"\n") {
		return errors.New("Не совпадает Developer ID или идентификатор Forge.")
	}
	return command(2*time.Minute, "/usr/sbin/spctl", "--assess", "--type", "execute", app)
}

// Roll back only our rename; never delete/overwrite a path created by another process.
func replaceWithBackup(app, candidate, backup string, rename func(string, string) error, lstat func(string) (os.FileInfo, error)) error {
	if _, err := lstat(backup); !os.IsNotExist(err) {
		return errors.New("Путь резервной копии уже существует или недоступен.")
	}
	if err := rename(app, backup); err != nil {
		return err
	}
	if err := rename(candidate, app); err != nil {
		if _, exists := lstat(app); os.IsNotExist(exists) {
			if rollback := rename(backup, app); rollback != nil {
				return errors.New("Не удалось вернуть приложение; сохранённая копия осталась рядом.")
			}
		}
		return err
	}
	return nil
}
