package com.syntec.clockapp.viewmodel

import android.os.SystemClock
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

enum class PomodoroPhase(val label: String, val emoji: String, val durationMs: Long) {
    IDLE       ("Idle",         "⏸",   0L),
    WORK       ("Work Session", "🍅",  25 * 60 * 1000L),
    SHORT_BREAK("Short Break",  "☕",   5 * 60 * 1000L),
    LONG_BREAK ("Long Break",   "🎉",  15 * 60 * 1000L),
}

data class PomodoroState(
    val phase:         PomodoroPhase = PomodoroPhase.IDLE,
    val completedWork: Int           = 0,
    val totalMs:       Long          = PomodoroPhase.WORK.durationMs,
    val remainingMs:   Long          = PomodoroPhase.WORK.durationMs,
    val isRunning:     Boolean       = false,
) {
    val progress: Float get() =
        if (totalMs == 0L) 1f else (1f - remainingMs.toFloat() / totalMs.toFloat()).coerceIn(0f, 1f)
}

/**
 * Pomodoro state machine with drift-free timing.
 *
 * Uses SystemClock.elapsedRealtime() as the reference instead of wall-clock
 * counting — so pausing, backgrounding, or GC pauses don't cause drift.
 * When the user backgrounds the app and returns, `remainingMs` is recalculated
 * from the elapsed monotonic clock, not from how many ticks fired.
 */
class PomodoroViewModel : ViewModel() {

    private val _state = MutableStateFlow(PomodoroState())
    val state: StateFlow<PomodoroState> = _state.asStateFlow()

    // elapsedRealtime() snapshot when the current run started
    private var runStartedAt   = 0L
    // How many ms were remaining when we last paused
    private var pausedRemaining = PomodoroPhase.WORK.durationMs

    private var tickJob: Job? = null

    // ── Controls ────────────────────────────────────────────────────────────

    fun startOrPause() {
        if (_state.value.isRunning) pause() else start()
    }

    fun start() {
        if (_state.value.phase == PomodoroPhase.IDLE) {
            transitionTo(PomodoroPhase.WORK)
        }
        runStartedAt = SystemClock.elapsedRealtime()
        _state.update { it.copy(isRunning = true) }
        scheduleTick()
    }

    fun pause() {
        tickJob?.cancel()
        pausedRemaining = currentRemaining()
        _state.update { it.copy(isRunning = false, remainingMs = pausedRemaining) }
    }

    fun reset() {
        tickJob?.cancel()
        pausedRemaining = PomodoroPhase.WORK.durationMs
        _state.value = PomodoroState()
    }

    fun skip() {
        tickJob?.cancel()
        onPhaseComplete()
    }

    // ── Lifecycle awareness: call on Activity/Fragment resume ────────────────

    /**
     * If a session was running in the background, recalculate remaining time
     * from the elapsed monotonic clock so we stay accurate after backgrounding.
     */
    fun onResume() {
        if (_state.value.isRunning) {
            val remaining = currentRemaining()
            if (remaining <= 0) {
                onPhaseComplete()
            } else {
                _state.update { it.copy(remainingMs = remaining) }
                scheduleTick()
            }
        }
    }

    // ── Internal ─────────────────────────────────────────────────────────────

    private fun currentRemaining(): Long {
        val elapsed = SystemClock.elapsedRealtime() - runStartedAt
        return (pausedRemaining - elapsed).coerceAtLeast(0L)
    }

    private fun scheduleTick() {
        tickJob?.cancel()
        tickJob = viewModelScope.launch {
            while (true) {
                delay(100L)
                val remaining = currentRemaining()
                _state.update { it.copy(remainingMs = remaining) }
                if (remaining <= 0L) {
                    onPhaseComplete()
                    break
                }
            }
        }
    }

    private fun onPhaseComplete() {
        tickJob?.cancel()
        val current = _state.value
        val nextPhase = when (current.phase) {
            PomodoroPhase.WORK         ->
                if ((current.completedWork + 1) % 4 == 0) PomodoroPhase.LONG_BREAK
                else PomodoroPhase.SHORT_BREAK
            PomodoroPhase.SHORT_BREAK,
            PomodoroPhase.LONG_BREAK   -> PomodoroPhase.WORK
            PomodoroPhase.IDLE         -> PomodoroPhase.WORK
        }
        val newCompleted = if (current.phase == PomodoroPhase.WORK) current.completedWork + 1 else current.completedWork
        transitionTo(nextPhase, newCompleted)
        // Auto-start next phase
        start()
    }

    private fun transitionTo(phase: PomodoroPhase, completedWork: Int = _state.value.completedWork) {
        pausedRemaining = phase.durationMs
        _state.update {
            it.copy(
                phase         = phase,
                completedWork = completedWork,
                totalMs       = phase.durationMs,
                remainingMs   = phase.durationMs,
                isRunning     = false,
            )
        }
    }
}
