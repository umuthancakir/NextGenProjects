package com.syntec.clockapp.ui

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.*
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.syntec.clockapp.R
import com.syntec.clockapp.databinding.FragmentWorldClockBinding
import com.syntec.clockapp.databinding.ItemWorldClockBinding
import com.syntec.clockapp.model.DEFAULT_WORLD_CLOCKS
import com.syntec.clockapp.model.WorldClock
import java.text.SimpleDateFormat
import java.util.*

class WorldClockFragment : Fragment() {

    private var _binding: FragmentWorldClockBinding? = null
    private val binding get() = _binding!!

    private lateinit var adapter: WorldClockAdapter
    private val handler = Handler(Looper.getMainLooper())

    private val ticker = object : Runnable {
        override fun run() {
            updateLocalTime()
            adapter.notifyDataSetChanged()
            handler.postDelayed(this, 1_000L)
        }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        _binding = FragmentWorldClockBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        adapter = WorldClockAdapter(DEFAULT_WORLD_CLOCKS)
        binding.rvWorldClocks.layoutManager = LinearLayoutManager(requireContext())
        binding.rvWorldClocks.adapter       = adapter
        updateLocalTime()
    }

    override fun onResume() {
        super.onResume()
        handler.post(ticker)
    }

    override fun onPause() {
        handler.removeCallbacks(ticker)
        super.onPause()
    }

    override fun onDestroyView() {
        handler.removeCallbacks(ticker)
        _binding = null
        super.onDestroyView()
    }

    private fun updateLocalTime() {
        val fmt = SimpleDateFormat("HH:mm:ss  EEEE, d MMM", Locale.getDefault())
        binding.tvLocalTime.text = "Your time: ${fmt.format(Date())}"
    }
}

// ── Adapter ───────────────────────────────────────────────────────────────────

class WorldClockAdapter(private val clocks: List<WorldClock>) :
    RecyclerView.Adapter<WorldClockAdapter.VH>() {

    inner class VH(val b: ItemWorldClockBinding) : RecyclerView.ViewHolder(b.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(ItemWorldClockBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun getItemCount() = clocks.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val wc       = clocks[position]
        val tz       = TimeZone.getTimeZone(wc.timezone)
        val cal      = Calendar.getInstance(tz)
        val localCal = Calendar.getInstance()

        val timeFmt = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        timeFmt.timeZone = tz

        val tzOffset  = tz.getOffset(System.currentTimeMillis()).toLong()
        val utcOffset = tzOffset / 3_600_000.0
        val sign      = if (utcOffset >= 0) "+" else ""
        val offsetStr = "UTC${sign}${utcOffset.toInt()}"

        holder.b.tvCityFlag.text  = "${wc.flag} ${wc.city}"
        holder.b.tvTimezone.text  = offsetStr
        holder.b.tvCityTime.text  = timeFmt.format(cal.time)

        // Day difference indicator
        val localDay  = localCal.get(Calendar.DAY_OF_YEAR)
        val remoteDay = cal.get(Calendar.DAY_OF_YEAR)
        val dayDiff   = remoteDay - localDay
        if (dayDiff != 0) {
            holder.b.tvDayIndicator.text       = if (dayDiff > 0) "+$dayDiff d" else "$dayDiff d"
            holder.b.tvDayIndicator.visibility = View.VISIBLE
        } else {
            holder.b.tvDayIndicator.visibility = View.GONE
        }
    }
}
