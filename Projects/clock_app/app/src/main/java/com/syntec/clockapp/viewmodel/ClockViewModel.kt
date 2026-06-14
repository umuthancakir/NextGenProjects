package com.syntec.clockapp.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.syntec.clockapp.util.SunriseSunset
import com.syntec.clockapp.util.TimeOfDayTheme
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.Calendar

data class ClockUiState(
    val calendar:      Calendar         = Calendar.getInstance(),
    val theme:         TimeOfDayTheme   = TimeOfDayTheme.NIGHT,
    val greeting:      String           = "",
    val dailyMessage:  String           = "",
    val sunriseMs:     Long?            = null,
    val sunsetMs:      Long?            = null,
    val sunDataReady:  Boolean          = false,
)

class ClockViewModel : ViewModel() {

    private val _state = MutableStateFlow(ClockUiState())
    val state: StateFlow<ClockUiState> = _state.asStateFlow()

    // Default coordinates: Istanbul (overridden by fragment when location permission granted)
    private var lat = 41.0082
    private var lon = 28.9784

    init {
        startTicker()
        computeSunData()
    }

    private fun startTicker() {
        viewModelScope.launch {
            while (true) {
                val cal   = Calendar.getInstance()
                val hour  = cal.get(Calendar.HOUR_OF_DAY)
                val theme = TimeOfDayTheme.forHour(hour)
                // Day-of-week index (Calendar.SUNDAY = 1 ... Calendar.SATURDAY = 7)
                val dow   = cal.get(Calendar.DAY_OF_WEEK) - 1 // 0-indexed

                _state.update { it.copy(calendar = cal, theme = theme, greeting = theme.greeting) }

                delay(500L)
            }
        }
    }

    fun updateLocation(latitude: Double, longitude: Double) {
        lat = latitude
        lon = longitude
        computeSunData()
    }

    private fun computeSunData() {
        viewModelScope.launch {
            val result = SunriseSunset.calculate(lat, lon)
            _state.update {
                it.copy(
                    sunriseMs    = result?.sunriseMs,
                    sunsetMs     = result?.sunsetMs,
                    sunDataReady = true,
                )
            }
        }
    }
}
