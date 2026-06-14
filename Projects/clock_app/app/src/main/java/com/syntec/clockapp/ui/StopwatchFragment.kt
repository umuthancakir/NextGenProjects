package com.syntec.clockapp.ui

import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.*
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.syntec.clockapp.databinding.FragmentStopwatchBinding
import com.syntec.clockapp.databinding.ItemLapBinding
import java.util.Locale

data class Lap(val number: Int, val lapMs: Long, val totalMs: Long)

class StopwatchFragment : Fragment() {

    private var _binding: FragmentStopwatchBinding? = null
    private val binding get() = _binding!!

    // Drift-free timing: track the monotonic clock at start, accumulate across pauses
    private var accumulated   = 0L   // ms accumulated before the last start
    private var startElapsed  = 0L   // elapsedRealtime() when the current run began
    private var isRunning     = false

    private val laps = mutableListOf<Lap>() // newest first

    private val handler = Handler(Looper.getMainLooper())
    private val ticker  = object : Runnable {
        override fun run() {
            updateDisplay()
            handler.postDelayed(this, 16)  // ~60fps for smooth centiseconds
        }
    }

    private lateinit var adapter: LapAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        _binding = FragmentStopwatchBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        adapter = LapAdapter(laps)
        binding.rvLaps.layoutManager = LinearLayoutManager(requireContext())
        binding.rvLaps.adapter       = adapter

        binding.btnStopwatchStartStop.setOnClickListener { toggleStartStop() }
        binding.btnStopwatchLap.setOnClickListener      { recordLap()       }
        binding.btnStopwatchReset.setOnClickListener    { reset()           }
    }

    override fun onDestroyView() {
        handler.removeCallbacks(ticker)
        _binding = null
        super.onDestroyView()
    }

    // ── Controls ─────────────────────────────────────────────────────────────

    private fun toggleStartStop() {
        if (isRunning) {
            // Pause: accumulate elapsed so far
            accumulated += SystemClock.elapsedRealtime() - startElapsed
            isRunning    = false
            handler.removeCallbacks(ticker)
            binding.btnStopwatchStartStop.text = "Start"
            binding.btnStopwatchLap.isEnabled  = false
        } else {
            startElapsed = SystemClock.elapsedRealtime()
            isRunning    = true
            handler.post(ticker)
            binding.btnStopwatchStartStop.text = "Stop"
            binding.btnStopwatchLap.isEnabled  = true
            binding.btnStopwatchReset.isEnabled = true
        }
    }

    private fun recordLap() {
        val total   = elapsed()
        val lapMs   = if (laps.isEmpty()) total else total - laps[0].totalMs
        laps.add(0, Lap(laps.size + 1, lapMs, total))
        adapter.notifyItemInserted(0)
        highlightFastestSlowest()
    }

    private fun reset() {
        handler.removeCallbacks(ticker)
        isRunning   = false
        accumulated = 0L
        laps.clear()
        adapter.notifyDataSetChanged()
        binding.tvStopwatchTime.text        = "00:00.00"
        binding.btnStopwatchStartStop.text  = "Start"
        binding.btnStopwatchLap.isEnabled   = false
        binding.btnStopwatchReset.isEnabled = false
    }

    // ── Timing ───────────────────────────────────────────────────────────────

    private fun elapsed(): Long {
        return if (isRunning) accumulated + SystemClock.elapsedRealtime() - startElapsed
        else accumulated
    }

    private fun updateDisplay() {
        binding.tvStopwatchTime.text = formatMs(elapsed())
    }

    private fun highlightFastestSlowest() {
        adapter.fastestIndex = -1
        adapter.slowestIndex = -1
        if (laps.size < 2) { adapter.notifyDataSetChanged(); return }

        val lapTimes   = laps.map { it.lapMs }
        val minMs      = lapTimes.min()
        val maxMs      = lapTimes.max()
        adapter.fastestIndex = laps.indexOfFirst { it.lapMs == minMs }
        adapter.slowestIndex = laps.indexOfFirst { it.lapMs == maxMs }
        adapter.notifyDataSetChanged()
    }

    companion object {
        fun formatMs(ms: Long): String {
            val cs  = (ms / 10) % 100
            val sec = (ms / 1000) % 60
            val min = ms / 60_000
            return String.format(Locale.US, "%02d:%02d.%02d", min, sec, cs)
        }
    }
}

// ── Adapter ───────────────────────────────────────────────────────────────────

class LapAdapter(private val laps: MutableList<Lap>) : RecyclerView.Adapter<LapAdapter.VH>() {

    var fastestIndex = -1
    var slowestIndex = -1

    inner class VH(val b: ItemLapBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
        VH(ItemLapBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun getItemCount() = laps.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val lap   = laps[position]
        val color = when (position) {
            fastestIndex -> Color.parseColor("#22C55E")
            slowestIndex -> Color.parseColor("#EF4444")
            else         -> Color.parseColor("#E2E8F0")
        }
        holder.b.tvLapNumber.text = "Lap ${lap.number}"
        holder.b.tvLapTime.text   = StopwatchFragment.formatMs(lap.lapMs)
        holder.b.tvLapTotal.text  = StopwatchFragment.formatMs(lap.totalMs)
        holder.b.tvLapTime.setTextColor(color)

        if (position == fastestIndex || position == slowestIndex) {
            val badge = if (position == fastestIndex) "⚡ Fastest" else "🐢 Slowest"
            holder.b.tvLapBadge.text       = badge
            holder.b.tvLapBadge.setTextColor(color)
            holder.b.tvLapBadge.visibility = View.VISIBLE
        } else {
            holder.b.tvLapBadge.visibility = View.GONE
        }
    }
}
