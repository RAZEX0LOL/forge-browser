package main

var locale = "ru"

var english = map[string]string{
	"Отмена":     "Cancel",
	"Продолжить": "Continue",
	"Обновление не установлено. Проверь подключение, часы и права на папку приложения. Профиль не изменён. ":                                                                                                                            "Update not installed. Check your connection, clock and application-folder permissions. Your profile was not changed. ",
	"Проверить подписанное обновление на razex.shop? Сервер получит IP-адрес и запрос updater, но не историю, вкладки или cookies. Проверка только вручную. Это development-канал без гарантии своевременных исправлений безопасности.": "Check razex.shop for a signed update? The server receives your IP address and an updater request, not history, tabs or cookies. Checks are manual only. This development channel has no guaranteed security-update service.",
	"Доступен Forge %s (%d МиБ). Скачать полный пакет? Потребуется закрыть браузер и отдельно подтвердить замену приложения. Прежнее приложение останется рядом для отката; профиль не изменяется.":                                     "Forge %s is available (%d MiB). Download the full package? You must close the browser and separately confirm replacement. The old application is retained beside it for rollback; your profile is not changed.",
	"Пакет проверен: SHA-256, размер, Developer ID, идентификатор приложения и Gatekeeper. Закрой все окна Forge, затем нажми «Продолжить» для замены. Ничего не будет установлено, пока браузер работает.":                             "Package verified: SHA-256, size, Developer ID, application identifier and Gatekeeper. Quit Forge completely, then choose Continue to replace it. Nothing will be installed while the browser is running.",
	"Forge обновлён. Запусти Forge.app обычным способом. Прежнее приложение сохранено рядом как .backup; профиль остался на месте.":                                                                                                     "Forge updated. Launch Forge.app normally. The previous application is retained beside it as .backup; your profile remains in place.",
	"Более нового совместимого пакета Forge нет.":                      "No newer compatible Forge package is available.",
	"Путь приложения или служебной папки недоступен/содержит симлинк.": "The application or update-state path is unavailable or contains a symlink.",
	"Запускай updater только из установленного Forge.app.":             "Run the updater only from an installed Forge.app.",
	"Ожидается Forge.app.":                   "Expected Forge.app.",
	"Ошибка HTTPS-запроса обновления.":       "Update HTTPS request failed.",
	"Неподходящий ответ сервера обновлений.": "Unexpected update-server response.",
	"Updater уже запущен либо остался lock после сбоя. Не запускай второй экземпляр.":    "The updater is already running, or a lock remains after a crash. Do not start a second instance.",
	"Некорректное состояние защиты от отката.":                                           "Invalid rollback-protection state.",
	"Неподдерживаемая архитектура.":                                                      "Unsupported architecture.",
	"Подпись, срок или параметры манифеста не прошли проверку.":                          "Manifest signature, expiry or parameters could not be verified.",
	"Нет прав на папку приложения. Установи пакет вручную; updater не запрашивает root.": "The application folder is not writable. Install the package manually; the updater does not request root access.",
	"Манифест истёк во время скачивания.":                                                "The manifest expired during download.",
	"Системная проверка/операция пакета отклонена.":                                      "The operating system rejected a package check or operation.",
	"Не совпадает Developer ID или идентификатор Forge.":                                 "Developer ID or Forge application identifier does not match.",
	"Не удалось проверить процессы браузера.":                                            "Could not check running browser processes.",
	"Сначала закрой Forge; приложение не заменено.":                                      "Quit Forge first; the application was not replaced.",
	"Путь резервной копии уже существует или недоступен.":                                "The backup path already exists or is unavailable.",
	"Не удалось вернуть приложение; сохранённая копия осталась рядом.":                   "The application could not be restored; its saved copy remains beside it.",
}

func tr(message string) string {
	if locale == "en" {
		if value, ok := english[message]; ok {
			return value
		}
	}
	return message
}
