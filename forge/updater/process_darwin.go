//go:build darwin && cgo

package main

/*
#cgo LDFLAGS: -lproc
#include <libproc.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>

// Never read argv. On privacy-restricted processes, return the kernel executable
// basename so Go can fail closed for any executable that exists in this bundle.
static int forge_process_path(int pid, char *buffer, unsigned int size, char *name, unsigned int name_size) {
    if (proc_pidpath(pid, buffer, size) > 0) return 1;
    if (kill(pid, 0) < 0 && errno == ESRCH) return 0;
    struct proc_bsdinfo info;
    memset(&info, 0, sizeof(info));
    if (proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, sizeof(info)) == sizeof(info)) {
        if (info.pbi_status == 5) return 0; // Darwin SZOMB: no executable is running.
        if (info.pbi_name[0]) snprintf(name, name_size, "%.*s", (int)sizeof(info.pbi_name), info.pbi_name);
        else snprintf(name, name_size, "%.*s", (int)sizeof(info.pbi_comm), info.pbi_comm);
        if (name[0]) return -2;
    }
    if (kill(pid, 0) < 0 && errno == ESRCH) return 0;
    return -1;
}
*/
import "C"

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"unsafe"
)

func noRunningBrowser(app string) error {
	executables := make(map[string]bool)
	err := filepath.WalkDir(app, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if !entry.IsDir() {
			info, err := entry.Info()
			if err != nil {
				return err
			}
			if info.Mode().Perm()&0o111 != 0 {
				executables[entry.Name()] = true
			}
		}
		return nil
	})
	if err != nil {
		return errors.New("Не удалось проверить процессы браузера.")
	}
	count := int(C.proc_listallpids(nil, 0))
	if count <= 0 || count > 100000 {
		return errors.New("Не удалось проверить процессы браузера.")
	}
	pids := make([]C.int, count+1024)
	n := int(C.proc_listallpids(unsafe.Pointer(&pids[0]), C.int(len(pids)*4)))
	if n <= 0 || n >= len(pids) {
		return errors.New("Не удалось проверить процессы браузера.")
	}
	for _, pid := range pids[:n] {
		if pid <= 0 || int(pid) == os.Getpid() {
			continue
		}
		var buffer [4096]C.char
		var name [64]C.char
		status := C.forge_process_path(pid, &buffer[0], C.uint(len(buffer)), &name[0], C.uint(len(name)))
		if status == -2 {
			kernelName := C.GoString(&name[0])
			for executable := range executables {
				if strings.HasPrefix(executable, kernelName) || strings.HasPrefix(kernelName, executable) {
					return errors.New("Не удалось проверить процессы браузера.")
				}
			}
			continue
		}
		if status < 0 {
			return errors.New("Не удалось проверить процессы браузера.")
		}
		if status > 0 && strings.HasPrefix(C.GoString(&buffer[0]), app+string(os.PathSeparator)) {
			return errors.New("Сначала закрой Forge; приложение не заменено.")
		}
	}
	return nil
}
