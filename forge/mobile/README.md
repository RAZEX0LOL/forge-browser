# Forge mobile prototypes

These are **new, minimal mobile applications**, not a port of the desktop XUL
interface, not Firefox/Fenix with a changed name, and not stable browsers.

| Project | Engine | Initial scope |
| --- | --- | --- |
| Android | Mozilla GeckoView `159.0.20261022150525` | HTTPS navigation/search, back/forward/reload, native address field, ru/en strings |
| iOS/iPadOS | Apple's system WKWebView | HTTPS navigation/search, back/forward/reload, native address field, phone/tablet layout |

Both start without remote page navigation and reject active/local/external URL
schemes and credential-bearing URLs. Neither overrides certificate failures.
This is not a claim that the underlying engine or OS sends no background traffic.
HTTP is deliberately unsupported in these initial prototypes. Search goes to
DuckDuckGo only when the person submits a search. Popups, downloads, permissions,
password management, extensions, multiple tabs/workspaces, desktop themes, browser
sync and durable session restoration are not implemented. Data is local to the
app; Android backup is disabled. No telemetry SDK is added, but these apps have
not received a full engine/network privacy audit. Desktop privacy claims and
test counts must not be applied to them.

## Android

JDK 17, compile SDK 37 (target SDK 35), Gradle 9.3.1, Android Gradle Plugin 9.1.1.
The engine is downloaded over HTTPS from Mozilla's Maven repository and is
independently versioned from desktop Gecko. Its exact source and license notices
are available from the same Maven coordinates (`-sources.jar`) and Mozilla.
The full native engine source revision declared by that version's official POM is
[`5add844c26613d7e4d84c799d6e23cf987b1240d`](https://hg.mozilla.org/releases/mozilla-release/rev/5add844c26613d7e4d84c799d6e23cf987b1240d).
This differs from the desktop source base. GeckoView also has AndroidX, Kotlin,
media and FIDO dependencies with their own applicable licenses; their upstream
notices are not replaced by Forge's MPL notice.
No production signing keys are committed.

```sh
cd android
gradle --no-daemon :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

The resulting APK uses a development/debug signing identity, not a stable
publisher key. A successful compile is not a device or emulator runtime test.
Separate APKs are generated for arm64-v8a, armeabi-v7a and x86_64; choose the
matching ABI rather than downloading every engine architecture in one APK.
Native CI runtime tests currently exercise x86_64 in an Android emulator, not
physical ARM phones. The prototype does not register itself as the default browser.

## iOS / iPadOS

Xcode + XcodeGen, minimum iOS 17. Uses **WebKit**, not Gecko. It is not a claim of
Apple alternative-engine eligibility, App Store review, or iPhone distribution.

```sh
cd ios
xcodegen generate
xcodebuild -project ForgeMobile.xcodeproj -scheme ForgeMobile -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
```

Simulator `.app` archives cannot be installed as an iPhone IPA. Device distribution
requires an appropriate Apple account, provisioning and signing; no personal
credentials, team IDs or signing material are assumed or uploaded.
The workflow also compiles an **unsigned device `.xcarchive`** for developers.
It is not an installable or App Store-approved IPA and does not bypass provisioning.

The mobile workflow is manually dispatched and uploads only development artifacts,
not automatic public releases. Source is MPL-2.0, with engine/platform licenses
remaining applicable.
