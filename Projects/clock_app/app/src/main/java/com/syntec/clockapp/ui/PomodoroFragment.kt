package com.syntec.clockapp.ui

import android.graphics.Color
import android.os.Bundle
import android.view.*
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.lifecycleScope
import com.syntec.clockapp.databinding.FragmentPomodoroBinding
import com.syntec.clockapp.viewmodel.PomodoroPhase
import com.syntec.clockapp.viewmodel.PomodoroViewModel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.util.Locale

class PomodoroFragment : Fragment() {

    private var _binding: FragmentPomodoroBinding? = null
    private val binding get() = _binding!!

    private val vm: PomodoroViewModel by viewModels()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        _binding = FragmentPomodoroBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupButtons()
        observeState()
    }

    override fun onResume() {
        super.onResume()
        // Recalculate remaining from monotonic clock — handles backgrounding correctly
        vm.onResume()
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }

    private fun setupButtons() {
        binding.btnStartPause.setOnClickListener { vm.startOrPause() }
        binding.btnReset.setOnClickListener      { vm.reset()        }
        binding.btnSkip.setOnClickListener       { vm.skip()         }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            vm.state.collectLatest { s ->
                // Timer display
                val min = s.remainingMs / 60_000
                val sec = (s.remainingMs / 1000) % 60
                binding.tvTimeRemaining.text = String.format(Locale.US, "%02d:%02d", min, sec)

                // Phase label + emoji
                binding.tvPhaseLabel.text  = s.phase.label
                binding.tvPhaseEmoji.text  = s.phase.emoji

                // Session count
                binding.tvSessionCount.text = "Session ${(s.completedWork % 4) + 1} / 4"

                // Button label
                binding.btnStartPause.text = if (s.isRunning) "Pause" else "Start"

                // Progress ring colour changes with phase
                val ringColor = when (s.phase) {
                    PomodoroPhase.WORK         -> Color.parseColor("#EF4444")
                    PomodoroPhase.SHORT_BREAK  -> Color.parseColor("#22C55E")
                    PomodoroPhase.LONG_BREAK   -> Color.parseColor("#3B82F6")
                    PomodoroPhase.IDLE         -> Color.parseColor("#475569")
                }
                binding.progressRing.ringColor = ringColor
                binding.progressRing.setProgress(s.progress)

                // Session dots (🍅 per completed work session in the current set of 4)
                binding.llSessionDots.removeAllViews()
                for (i in 0 until 4) {
                    val dot = TextView(requireContext()).apply {
                        text     = if (i < s.completedWork % 4 ||
                            (s.completedWork > 0 && s.completedWork % 4 == 0 && i < 4)) "🍅" else "⬜"
                        textSize = 20f
                    }
                    binding.llSessionDots.addView(dot)
                }
            }
        }
    }
}
