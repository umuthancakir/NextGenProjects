package com.syntec.clockapp.views

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import kotlin.math.min

/**
 * Circular progress ring for the Pomodoro timer.
 * Animates smoothly when progress changes using ValueAnimator.
 * Ring colour and stroke width are configurable at runtime.
 */
class ProgressRingView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    /** 0.0 = empty, 1.0 = full */
    private var displayedProgress = 1f
    private var targetProgress    = 1f
    private var animator: ValueAnimator? = null

    var ringColor: Int = Color.parseColor("#EF4444")
        set(value) { field = value; ringPaint.color = value; invalidate() }

    var strokeWidthDp: Float = 14f
        set(value) {
            field = value
            val density = resources.displayMetrics.density
            ringPaint.strokeWidth  = value * density
            trackPaint.strokeWidth = value * density
            invalidate()
        }

    private val density = context.resources.displayMetrics.density

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style       = Paint.Style.STROKE
        strokeCap   = Paint.Cap.ROUND
        color       = Color.parseColor("#1E1E3A")
        strokeWidth = 14f * density
    }

    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style       = Paint.Style.STROKE
        strokeCap   = Paint.Cap.ROUND
        color       = Color.parseColor("#EF4444")
        strokeWidth = 14f * density
    }

    private val oval = RectF()

    fun setProgress(progress: Float, animate: Boolean = true) {
        val clamped = progress.coerceIn(0f, 1f)
        if (!animate) {
            displayedProgress = clamped
            targetProgress    = clamped
            invalidate()
            return
        }
        targetProgress = clamped
        animator?.cancel()
        animator = ValueAnimator.ofFloat(displayedProgress, clamped).apply {
            duration = 400L
            addUpdateListener {
                displayedProgress = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    override fun onDraw(canvas: Canvas) {
        val pad  = ringPaint.strokeWidth / 2f + 2f
        val cx   = width / 2f
        val cy   = height / 2f
        val r    = min(cx, cy) - pad

        oval.set(cx - r, cy - r, cx + r, cy + r)

        // Background track
        canvas.drawOval(oval, trackPaint)

        // Progress arc — starts at top (−90°), sweeps clockwise
        val sweep = displayedProgress * 360f
        if (sweep > 0f) {
            canvas.drawArc(oval, -90f, sweep, false, ringPaint)
        }
    }
}
