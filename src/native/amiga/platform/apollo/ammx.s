; AMMX for amigentd.apollo only. vasmm68k_mot -m68080.
; Arguments arrive on the stack: gcc for this tree is not -mregparm.
;   LONG ammx_differs(const UBYTE *a, const UBYTE *b, LONG n);  n multiple of 8
;   void ammx_rgb332(const UBYTE *rgb, UBYTE *dst, LONG pixels); pixels multiple of 4

	section	code,code
	xdef	_ammx_differs
	xdef	_ammx_rgb332

_ammx_differs:
	move.l	4(sp),a0
	move.l	8(sp),a1
	move.l	12(sp),d0
	lsr.l	#3,d0
	beq.s	.same
	subq.l	#1,d0
.cmp:
	load	(a0),e0
	load	(a1),e1
	addq.l	#8,a0
	addq.l	#8,a1
	peor	e1,e0,e2
	subq.l	#8,sp
	store	e2,(sp)
	move.l	(sp),d1
	or.l	4(sp),d1
	addq.l	#8,sp
	bne.s	.diff
	dbra	d0,.cmp
.same:
	moveq	#0,d0
	rts
.diff:
	moveq	#1,d0
	rts

; Four pixels a step. PMULH by 2048 keeps the top of each 16-bit channel,
; which is that byte shifted right by 5. B keeps its top two bits.
_ammx_rgb332:
	movem.l	d2-d7/a2,-(sp)
	lea	-16(sp),sp
	move.l	48(sp),a0
	move.l	52(sp),a1
	move.l	56(sp),d7
	lsr.l	#2,d7
	beq.s	.out
	subq.l	#1,d7
	load.w	#$0800,e4
.pix:
	moveq	#0,d0
	move.b	(a0),d0
	moveq	#0,d1
	move.b	3(a0),d1
	moveq	#0,d2
	move.b	6(a0),d2
	moveq	#0,d3
	move.b	9(a0),d3
	move.w	d0,(sp)
	move.w	d1,2(sp)
	move.w	d2,4(sp)
	move.w	d3,6(sp)
	load	(sp),e0
	pmulh	e4,e0,e1
	store	e1,8(sp)
	moveq	#0,d0
	move.b	1(a0),d0
	moveq	#0,d1
	move.b	4(a0),d1
	moveq	#0,d2
	move.b	7(a0),d2
	moveq	#0,d3
	move.b	10(a0),d3
	move.w	d0,(sp)
	move.w	d1,2(sp)
	move.w	d2,4(sp)
	move.w	d3,6(sp)
	load	(sp),e0
	pmulh	e4,e0,e2
	store	e2,(sp)
	move.w	8(sp),d0
	move.w	(sp),d1
	move.b	2(a0),d2
	bsr	.mix
	move.b	d0,(a1)+
	move.w	10(sp),d0
	move.w	2(sp),d1
	move.b	5(a0),d2
	bsr	.mix
	move.b	d0,(a1)+
	move.w	12(sp),d0
	move.w	4(sp),d1
	move.b	8(a0),d2
	bsr	.mix
	move.b	d0,(a1)+
	move.w	14(sp),d0
	move.w	6(sp),d1
	move.b	11(a0),d2
	bsr	.mix
	move.b	d0,(a1)+
	lea	12(a0),a0
	dbra	d7,.pix
.out:
	lea	16(sp),sp
	movem.l	(sp)+,d2-d7/a2
	rts
; d0 = R>>5, d1 = G>>5, d2 = B. Result in d0. Does not use the stack.
.mix:
	and.w	#7,d0
	and.w	#7,d1
	lsl.w	#3,d1
	or.w	d1,d0
	and.b	#$c0,d2
	or.b	d2,d0
	rts

	end
