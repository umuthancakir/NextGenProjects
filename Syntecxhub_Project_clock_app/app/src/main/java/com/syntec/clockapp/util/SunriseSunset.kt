package com.syntec.clockapp.util

import java.util.Calendar
import java.util.TimeZone
import kotlin.math.*

/**
 * Pure-math sunrise/sunset calculator using the NOAA solar algorithm.
 * No external library required — accurate to within a minute for most latitudes.
 */
object SunriseSunset {

    data class Result(val sunriseMs: Long, val sunsetMs: Long)

    /**
     * @param lat  latitude  in degrees (positive = North)
     * @param lon  longitude in degrees (positive = East)
     * @return Result with epoch-millisecond timestamps for today, or null if polar day/night.
     */
    fun calculate(lat: Double, lon: Double): Result? {
        val tz  = TimeZone.getDefault()
        val cal = Calendar.getInstance(tz)
        val jd  = julianDay(cal)
        val d   = jd - 2451545.0

        // Mean anomaly + solar longitude
        val gRad = Math.toRadians((357.529 + 0.98560028 * d).mod(360.0))
        val q    = (280.459 + 0.98564736 * d).mod(360.0)
        val lRad = Math.toRadians((q + 1.915 * sin(gRad) + 0.020 * sin(2 * gRad)).mod(360.0))

        // Obliquity
        val eRad = Math.toRadians(23.439 - 0.0000004 * d)

        // Declination and right ascension
        val sinDec  = sin(eRad) * sin(lRad)
        val cosDec  = cos(asin(sinDec))
        val raHours = Math.toDegrees(atan2(cos(eRad) * sin(lRad), cos(lRad))) / 15.0

        // Equation of time (simplified)
        val eqt = raHours - q / 15.0

        // Solar noon in UTC hours
        val solarNoonUTC = 12.0 - lon / 15.0 - eqt

        // Hour angle for sunrise/sunset (official zenith = 90.833°)
        val cosH = (cos(Math.toRadians(90.833)) - sinDec * sin(Math.toRadians(lat))) /
                   (cosDec * cos(Math.toRadians(lat)))

        if (cosH < -1 || cosH > 1) return null // polar day / night

        val h = Math.toDegrees(acos(cosH)) / 15.0

        val sunriseUTC = solarNoonUTC - h
        val sunsetUTC  = solarNoonUTC + h

        return Result(utcHoursToEpoch(cal, sunriseUTC), utcHoursToEpoch(cal, sunsetUTC))
    }

    private fun utcHoursToEpoch(localCal: Calendar, utcHours: Double): Long {
        val c = localCal.clone() as Calendar
        c.timeZone = TimeZone.getTimeZone("UTC")
        c.set(Calendar.HOUR_OF_DAY, utcHours.toInt())
        c.set(Calendar.MINUTE, ((utcHours % 1.0) * 60).toInt())
        c.set(Calendar.SECOND, 0)
        c.set(Calendar.MILLISECOND, 0)
        return c.timeInMillis
    }

    private fun julianDay(cal: Calendar): Double {
        val y = cal.get(Calendar.YEAR)
        val m = cal.get(Calendar.MONTH) + 1
        val d = cal.get(Calendar.DAY_OF_MONTH)
        // Julian Day Number formula (Meeus algorithm, accurate for years 1801-2099)
        val a = (14 - m) / 12
        val yr = y + 4800 - a
        val mo = m + 12 * a - 3
        return d + (153 * mo + 2) / 5 + 365L * yr + yr / 4 - yr / 100 + yr / 400 - 32045 - 0.5
    }
}
