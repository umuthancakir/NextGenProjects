package com.syntec.clockapp.service

import android.app.*
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import com.syntec.clockapp.MainActivity
import com.syntec.clockapp.R
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.util.Locale

/**
 * Foreground service that keeps a countdown timer alive when the app is backgrounded.
 *
 * Uses SystemClock.elapsedRealtime() for drift-free elapsed time rather than
 * counting handler ticks, which can drift under GC pressure or CPU throttling.
 * Fires a notification when the countdown reaches zero.
 */
class TimerForegroundService : Service() {

    inner class LocalBinder : Binder() {
        fun getService() = this@TimerForegroundService
    }

    private val binder  = LocalBinder()
    private val scope   = CoroutineScope(Dispatchers.Default + SupervisorJob())

    private var startElapsedMs    = 0L
    private var pausedRemainingMs = 0L
    private var totalMs           = 0L
    private var running           = false

    private val _remaining = MutableStateFlow(0L)
    val remaining: StateFlow<Long> = _remaining.asStateFlow()

    private var tickJob: Job? = null

    // ── Service lifecycle ────────────────────────────────────────────────────

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START  -> {
                totalMs           = intent.getLongExtra(EXTRA_DURATION_MS, 25 * 60 * 1000L)
                pausedRemainingMs = totalMs
                startTimer()
            }
            ACTION_PAUSE  -> pauseTimer()
            ACTION_CANCEL -> cancelTimer()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    // ── Timer logic ──────────────────────────────────────────────────────────

    fun startTimer() {
        running        = true
        startElapsedMs = SystemClock.elapsedRealtime()

        startForeground(NOTIFICATION_ID, buildNotification(pausedRemainingMs))

        tickJob?.cancel()
        tickJob = scope.launch {
            while (running) {
                delay(500)
                val elapsed   = SystemClock.elapsedRealtime() - startElapsedMs
                val remaining = (pausedRemainingMs - elapsed).coerceAtLeast(0L)
                _remaining.value = remaining
                updateNotification(remaining)

                if (remaining == 0L) {
                    fireCompletionNotification()
                    stopSelf()
                    break
                }
            }
        }
    }

    fun pauseTimer() {
        running           = false
        pausedRemainingMs = _remaining.value
        tickJob?.cancel()
        updateNotification(pausedRemainingMs)
    }

    fun cancelTimer() {
        running = false
        tickJob?.cancel()
        stopForeground(true)
        stopSelf()
    }

    // ── Notifications ────────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.timer_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(remainingMs: Long): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(getString(R.string.timer_notification_title))
            .setContentText(formatMs(remainingMs))
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun updateNotification(remainingMs: Long) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(remainingMs))
    }

    private fun fireCompletionNotification() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.cancel(NOTIFICATION_ID)
        val n = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(getString(R.string.pomodoro_done_title))
            .setContentText(getString(R.string.pomodoro_done_body))
            .setAutoCancel(true)
            .build()
        nm.notify(NOTIFICATION_DONE_ID, n)
    }

    private fun formatMs(ms: Long): String {
        val s   = ms / 1000
        val min = s / 60
        val sec = s % 60
        return String.format(Locale.US, "%02d:%02d", min, sec)
    }

    companion object {
        const val CHANNEL_ID        = "timer_channel"
        const val NOTIFICATION_ID      = 1001
        const val NOTIFICATION_DONE_ID = 1002
        const val ACTION_START      = "action_start"
        const val ACTION_PAUSE      = "action_pause"
        const val ACTION_CANCEL     = "action_cancel"
        const val EXTRA_DURATION_MS = "extra_duration_ms"
    }
}
