package com.syntec.clockapp.views

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import androidx.core.animation.doOnEnd

/**
 * Single-digit view with a slot-machine style scroll animation.
 *
 * When the digit changes, the current digit slides upward and fades out while
 * the new digit slides in from below, creating a clean rolling effect.
 * Clip-rect confines both texts to the view bounds.
 */
class FlipClockView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    private var currentChar = '0'
    private var nextChar    = '0'
    private var progress    = 0f  // 0 = old digit only, 1 = new digit only
    private var animator: ValueAnimator? = null

    private val cornerRadius = 14f

    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#1A1E1E3A")
        style = Paint.Style.FILL
    }

    private val dividePaint = Paint().apply {
        color = Color.parseColor("#0A000000")
        strokeWidth = 1f
        style = Paint.Style.STROKE
    }

    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color   = Color.parseColor("#E2E8F0")
        typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textAlign = Paint.Align.CENTER
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        textPaint.textSize = h * 0.60f
    }

    fun setDigit(c: Char) {
        if (c == currentChar && progress == 0f) return
        val target = if (progress > 0.5f) nextChar else currentChar
        nextChar = c
        if (target == c) {
            animator?.cancel()
            currentChar = c
            progress = 0f
            invalidate()
            return
        }
        startRollAnimation()
    }

    private fun startRollAnimation() {
        animator?.cancel()
        animator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration    = 220L
            interpolator = AccelerateDecelerateInterpolator()
            addUpdateListener {
                progress = it.animatedValue as Float
                invalidate()
            }
            doOnEnd {
                currentChar = nextChar
                progress    = 0f
                invalidate()
            }
            start()
        }
    }

    override fun onDraw(canvas: Canvas) {
        val w  = width.toFloat()
        val h  = height.toFloat()
        val cx = w / 2f

        // Background card
        canvas.drawRoundRect(0f, 0f, w, h, cornerRadius, cornerRadius, bgPaint)

        // Clip everything to card bounds to contain the scroll
        canvas.save()
        canvas.clipRect(0f, 0f, w, h)

        val textMid = (textPaint.descent() + textPaint.ascent()) / 2f  // ascent is negative

        if (progress == 0f) {
            canvas.drawText(currentChar.toString(), cx, h / 2f - textMid, textPaint)
        } else {
            val shift = h * progress

            // Old digit scrolls up
            val oldAlpha = ((1f - progress) * 255f).toInt().coerceIn(0, 255)
            textPaint.alpha = oldAlpha
            canvas.drawText(currentChar.toString(), cx, h / 2f - textMid - shift, textPaint)

            // New digit comes up from below
            val newAlpha = (progress * 255f).toInt().coerceIn(0, 255)
            textPaint.alpha = newAlpha
            canvas.drawText(nextChar.toString(), cx, h / 2f - textMid + (h - shift), textPaint)

            textPaint.alpha = 255
        }

        canvas.restore()

        // Centre divider line (mimics the fold line of a real flip clock)
        canvas.drawLine(0f, h / 2f, w, h / 2f, dividePaint)
    }
}
