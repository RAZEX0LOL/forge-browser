package main

import (
	"context"
	"crypto/tls"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestNativeHTTPSDefaultsAndNoCookieJar(t *testing.T) {
	client := httpClient()
	transport := client.Transport.(*http.Transport)
	if !transport.DisableCompression || transport.TLSClientConfig.InsecureSkipVerify ||
		transport.TLSClientConfig.MinVersion < tls.VersionTLS12 || transport.TLSClientConfig.RootCAs != nil || client.Jar != nil {
		t.Fatal("platform TLS/cookie isolation changed")
	}
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.Header.Get("Cookie") != "" || request.Header.Get("Referer") != "" ||
			request.Header.Get("User-Agent") != "Forge-Desktop-Update/1" || request.Header.Get("Accept-Encoding") != "identity" {
			t.Error("unexpected updater request metadata")
		}
		writer.Header().Set("Set-Cookie", "fixture=must-not-persist")
		writer.Write([]byte("ok"))
	}))
	defer server.Close()
	for i := 0; i < 2; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		result, err := response(ctx, client, server.URL, 32)
		if err != nil {
			cancel()
			t.Fatal(err)
		}
		result.Body.Close()
		cancel()
	}
}

func TestRedirectsAndUnexpectedResponsesFailClosed(t *testing.T) {
	var redirected atomic.Int32
	destination := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) { redirected.Add(1) }))
	defer destination.Close()
	for _, kind := range []string{"redirect", "partial", "compressed", "oversize"} {
		t.Run(kind, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
				switch kind {
				case "redirect":
					http.Redirect(writer, request, destination.URL, http.StatusFound)
				case "partial":
					writer.WriteHeader(http.StatusPartialContent)
				case "compressed":
					writer.Header().Set("Content-Encoding", "gzip")
					writer.Write([]byte("bad"))
				case "oversize":
					writer.Header().Set("Content-Length", "1000")
					writer.Write([]byte("bad"))
				}
			}))
			defer server.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			if result, err := response(ctx, httpClient(), server.URL, 10); err == nil {
				result.Body.Close()
				t.Fatal("unsafe HTTP response accepted")
			}
		})
	}
	if redirected.Load() != 0 {
		t.Fatal("redirect target was contacted")
	}
}
