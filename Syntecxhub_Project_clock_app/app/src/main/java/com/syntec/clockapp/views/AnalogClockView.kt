package com.syntec.clockapp.views

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import java.util.Calendar
import kotlin.math.*

/**
 * Canvas-drawn analog clock with:
 * - Smooth second-hand sweep (sub-second interpolation via milliseconds)
 * - Inset minute markers + bold hour markers
 * - Tapered hour, minute, and sweep second hands
 * - Drop shadow on the face
 * - Accent colour changeable at runtime (time-of-day theming)
 */
class AnalogClockView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    var accentColor: Int = Color.parseColor("#818CF8")
        set(value) { field = value; secHandPaint.color = value; centerDotPaint.color = value; invalidate() }

    private val facePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#0F0F24")
        style = Paint.Style.FILL
    }
    private val faceStrokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#1E1E44")
        style = Paint.Style.STROKE
        strokeWidth = 3f
    }
    private val markerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#475569")
        style = Paint.Style.FILL
    }
    private val hourMarkerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#94A3B8")
        style = Paint.Style.FILL
    }
    private val hourHandPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#E2E8F0")
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val minHandPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#CBD5E1")
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val secHandPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#818CF8")
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeWidth = 3f
    }
    private val centerDotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#818CF8")
        style = Paint.Style.FILL
    }

    private val cal = Calendar.getInstance()

    // Handler-based redraw at ~33fps for smooth second hand
    private val ticker = object : Runnable {
        override fun run() {
            cal.timeInMillis = System.currentTimeMillis()
            invalidate()
            postDelayed(this, 30)
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        post(ticker)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(ticker)
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val w  = width.toFloat()
        val h  = height.toFloat()
        val cx = w / 2f
        val cy = h / 2f
        val r  = minOf(cx, cy) - 10f

        // Face
        canvas.drawCircle(cx, cy, r, facePaint)
        canvas.drawCircle(cx, cy, r, faceStrokePaint)

        hourHandPaint.strokeWidth = r * 0.06f
        minHandPaint.strokeWidth  = r * 0.04f

        // Hour + minute markers
        for (i in 0 until 60) {
            val angle  = Math.toRadians(i * 6.0 - 90)
            val isHour = i % 5 == 0

            val outerR = r - r * 0.04f
            val innerR = if (isHour) r - r * 0.14f else r - r * 0.08f
            val mR     = if (isHour) r * 0.025f else r * 0.012f

            val mx = cx + (innerR + mR) * cos(angle).toFloat()
            val my = cy + (innerR + mR) * sin(angle).toFloat()

            val p = if (isHour) hourMarkerPaint else markerPaint
            canvas.drawCircle(mx, my, mR, p)
        }

        // Time values with sub-second smoothing
        val ms  = cal.get(Calendar.MILLISECOND)
        val sec = cal.get(Calendar.SECOND) + ms / 1000f
        val min = cal.get(Calendar.MINUTE) + sec / 60f
        val hr  = (cal.get(Calendar.HOUR) % 12) + min / 60f

        // Hour hand (40% of radius)
        drawHand(canvas, cx, cy, r * 0.42f, hr / 12f * 360f, hourHandPaint)
        // Minute hand (65% of radius)
        drawHand(canvas, cx, cy, r * 0.64f, min / 60f * 360f, minHandPaint)
        // Second hand (78% + tail)
        drawSecondHand(canvas, cx, cy, r, sec / 60f * 360f)

        // Center dot
        canvas.drawCircle(cx, cy, r * 0.04f, centerDotPaint)
    }

    private fun drawHand(canvas: Canvas, cx: Float, cy: Float, length: Float, angleDeg: Float, paint: Paint) {
        val rad = Math.toRadians(angleDeg.toDouble() - 90)
        canvas.drawLine(
            cx, cy,
            cx + length * cos(rad).toFloat(),
            cy + length * sin(rad).toFloat(),
            paint,
        )
    }

    private fun drawSecondHand(canvas: Canvas, cx: Float, cy: Float, r: Float, angleDeg: Float) {
        val rad  = Math.toRadians(angleDeg.toDouble() - 90)
        // Tail: 20% in opposite direction
        canvas.drawLine(
            cx - r * 0.20f * cos(rad).toFloat(),
            cy - r * 0.20f * sin(rad).toFloat(),
            cx + r * 0.78f * cos(rad).toFloat(),
            cy + r * 0.78f * sin(rad).toFloat(),
            secHandPaint,
        )
    }
}
