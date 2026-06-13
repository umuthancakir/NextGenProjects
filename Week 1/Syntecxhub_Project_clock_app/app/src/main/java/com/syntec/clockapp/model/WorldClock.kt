package com.syntec.clockapp.model

data class WorldClock(
    val city:     String,
    val country:  String,
    val flag:     String,
    val timezone: String,
)

val DEFAULT_WORLD_CLOCKS = listOf(
    WorldClock("Istanbul",    "Turkey",     "🇹🇷", "Europe/Istanbul"),
    WorldClock("London",      "UK",         "🇬🇧", "Europe/London"),
    WorldClock("Paris",       "France",     "🇫🇷", "Europe/Paris"),
    WorldClock("New York",    "USA",        "🇺🇸", "America/New_York"),
    WorldClock("Los Angeles", "USA",        "🇺🇸", "America/Los_Angeles"),
    WorldClock("São Paulo",   "Brazil",     "🇧🇷", "America/Sao_Paulo"),
    WorldClock("Dubai",       "UAE",        "🇦🇪", "Asia/Dubai"),
    WorldClock("Singapore",   "Singapore",  "🇸🇬", "Asia/Singapore"),
    WorldClock("Tokyo",       "Japan",      "🇯🇵", "Asia/Tokyo"),
    WorldClock("Sydney",      "Australia",  "🇦🇺", "Australia/Sydney"),
)
