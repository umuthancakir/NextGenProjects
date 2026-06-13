package com.syntec.clockapp.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.lifecycleScope
import com.syntec.clockapp.databinding.FragmentClockBinding
import com.syntec.clockapp.viewmodel.ClockViewModel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.concurrent.TimeUnit

class ClockFragment : Fragment() {

    private var _binding: FragmentClockBinding? = null
    private val binding get() = _binding!!

    private val vm: ClockViewModel by viewModels()

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    private val locationPermLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) fetchLocation()
    }

    // ── Lifecycle ────────────────────────────────────────────────────────────

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        _binding = FragmentClockBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        initTts()
        requestLocationIfNeeded()
        observeState()
        setupButtons()
    }

    override fun onDestroyView() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        _binding = null
        super.onDestroyView()
    }

    // ── Setup ────────────────────────────────────────────────────────────────

    private fun initTts() {
        tts = TextToSpeech(requireContext()) { status ->
            ttsReady = (status == TextToSpeech.SUCCESS)
            if (ttsReady) tts?.language = Locale.getDefault()
        }
    }

    private fun requestLocationIfNeeded() {
        when {
            ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED -> fetchLocation()
            else -> locationPermLauncher.launch(Manifest.permission.ACCESS_COARSE_LOCATION)
        }
    }

    private fun fetchLocation() {
        try {
            val lm = requireContext().getSystemService(android.content.Context.LOCATION_SERVICE)
                as android.location.LocationManager
            val loc = lm.getLastKnownLocation(android.location.LocationManager.NETWORK_PROVIDER)
                ?: lm.getLastKnownLocation(android.location.LocationManager.GPS_PROVIDER)
            if (loc != null) vm.updateLocation(loc.latitude, loc.longitude)
        } catch (_: SecurityException) {}
    }

    private fun setupButtons() {
        binding.btnSpeak.setOnClickListener {
            if (!ttsReady) return@setOnClickListener
            val cal  = Calendar.getInstance()
            val hour = cal.get(Calendar.HOUR_OF_DAY)
            val min  = cal.get(Calendar.MINUTE)
            val text = "The time is ${hour % 12} ${String.format("%02d", min)}${if (hour < 12) " AM" else " PM"}"
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "speak_time")
        }
    }

    // ── State observation ────────────────────────────────────────────────────

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            vm.state.collectLatest { s ->
                val cal = s.calendar

                // Greeting + daily message
                binding.tvGreeting.text = s.theme.greeting
                val dayIndex = (cal.get(Calendar.DAY_OF_WEEK) - Calendar.SUNDAY)
                    .coerceIn(0, 6)
                val messages = resources.getStringArray(com.syntec.clockapp.R.array.daily_messages)
                binding.tvDailyMessage.text = messages.getOrNull(dayIndex) ?: ""

                // Date
                binding.tvDate.text = SimpleDateFormat("EEEE, d MMMM", Locale.getDefault()).format(cal.time)

                // Flip digit display: HH:MM:SS
                val hh = String.format("%02d", cal.get(Calendar.HOUR_OF_DAY))
                val mm = String.format("%02d", cal.get(Calendar.MINUTE))
                val ss = String.format("%02d", cal.get(Calendar.SECOND))

                binding.digitH1.setDigit(hh[0])
                binding.digitH2.setDigit(hh[1])
                binding.digitM1.setDigit(mm[0])
                binding.digitM2.setDigit(mm[1])
                binding.digitS1.setDigit(ss[0])
                binding.digitS2.setDigit(ss[1])

                // Analog clock accent colour
                binding.analogClock.accentColor = s.theme.accentColor

                // Sunrise/sunset
                if (s.sunDataReady) {
                    val fmt = SimpleDateFormat("HH:mm", Locale.getDefault())
                    binding.tvSunrise.text = s.sunriseMs?.let { fmt.format(it) } ?: "—"
                    binding.tvSunset.text  = s.sunsetMs?.let  { fmt.format(it) } ?: "—"

                    val now = System.currentTimeMillis()
                    if (s.sunriseMs != null && s.sunsetMs != null) {
                        val remaining = s.sunsetMs - now
                        binding.tvDaylightRemaining.text = when {
                            now < s.sunriseMs -> "before sunrise"
                            remaining > 0     -> {
                                val h = TimeUnit.MILLISECONDS.toHours(remaining)
                                val m = TimeUnit.MILLISECONDS.toMinutes(remaining) % 60
                                "${h}h ${m}m daylight left"
                            }
                            else -> "after sunset"
                        }
                    }
                }
            }
        }
    }
}
