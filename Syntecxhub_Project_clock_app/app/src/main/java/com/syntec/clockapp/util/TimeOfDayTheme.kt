package com.syntec.clockapp.util

import android.graphics.Color

/**
 * Maps the current hour to a visual theme — background, accent, and on-surface colors.
 * The Activity reads this every minute and cross-fades the window background.
 */
enum class TimeOfDayTheme(
    val displayName: String,
    val greeting:    String,
    val emoji:       String,
    val bgColor:     Int,
    val surfaceColor:Int,
    val accentColor: Int,
    val onColor:     Int,
) {
    MORNING(
        "Morning", "Good morning", "🌅",
        bgColor      = Color.parseColor("#FFF7ED"),
        surfaceColor = Color.parseColor("#FFFFFF"),
        accentColor  = Color.parseColor("#EA580C"),
        onColor      = Color.parseColor("#1C1917"),
    ),
    AFTERNOON(
        "Afternoon", "Good afternoon", "☀️",
        bgColor      = Color.parseColor("#EFF6FF"),
        surfaceColor = Color.parseColor("#FFFFFF"),
        accentColor  = Color.parseColor("#2563EB"),
        onColor      = Color.parseColor("#1E3A5F"),
    ),
    EVENING(
        "Evening", "Good evening", "🌆",
        bgColor      = Color.parseColor("#1E1B4B"),
        surfaceColor = Color.parseColor("#2D2B5E"),
        accentColor  = Color.parseColor("#EC4899"),
        onColor      = Color.parseColor("#E2E8F0"),
    ),
    NIGHT(
        "Night", "Good night", "🌙",
        bgColor      = Color.parseColor("#020617"),
        surfaceColor = Color.parseColor("#0F0F24"),
        accentColor  = Color.parseColor("#818CF8"),
        onColor      = Color.parseColor("#E2E8F0"),
    );

    companion object {
        fun forHour(hour: Int): TimeOfDayTheme = when (hour) {
            in 5..11  -> MORNING
            in 12..17 -> AFTERNOON
            in 18..20 -> EVENING
            else      -> NIGHT
        }
    }
}
