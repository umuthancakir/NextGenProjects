package com.syntec.clockapp

import android.animation.ArgbEvaluator
import android.animation.ValueAnimator
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import androidx.navigation.fragment.NavHostFragment
import androidx.navigation.ui.setupWithNavController
import com.syntec.clockapp.databinding.ActivityMainBinding
import com.syntec.clockapp.util.TimeOfDayTheme
import java.util.Calendar

/**
 * Single-activity host.
 *
 * Responsibility: apply the time-of-day adaptive background each minute.
 * The smooth colour crossfade (ArgbEvaluator + ValueAnimator) runs directly
 * on the root layout so all fragments inherit it without needing their own
 * background declarations.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private var currentTheme: TimeOfDayTheme? = null
    private val themeCheckRunnable = object : Runnable {
        override fun run() {
            applyThemeIfChanged()
            binding.root.postDelayed(this, 60_000L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Transparent status and nav bars for edge-to-edge look
        window.setFlags(
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
        )

        val navHost = supportFragmentManager
            .findFragmentById(R.id.navHostFragment) as NavHostFragment
        binding.bottomNav.setupWithNavController(navHost.navController)

        applyThemeIfChanged(animate = false)
        binding.root.post(themeCheckRunnable)
    }

    override fun onDestroy() {
        binding.root.removeCallbacks(themeCheckRunnable)
        super.onDestroy()
    }

    private fun applyThemeIfChanged(animate: Boolean = true) {
        val hour  = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val theme = TimeOfDayTheme.forHour(hour)
        if (theme == currentTheme) return

        val fromColor = currentTheme?.bgColor ?: theme.bgColor
        currentTheme  = theme

        if (!animate) {
            binding.mainRoot.setBackgroundColor(theme.bgColor)
            return
        }

        ValueAnimator.ofObject(ArgbEvaluator(), fromColor, theme.bgColor).apply {
            duration = 3_000L
            addUpdateListener { binding.mainRoot.setBackgroundColor(it.animatedValue as Int) }
            start()
        }
    }
}
