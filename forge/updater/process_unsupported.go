//go:build !darwin || !cgo

package main

import "errors"

func noRunningBrowser(string) error {
	return errors.New("Native process inspection is unavailable; installation is disabled.")
}
