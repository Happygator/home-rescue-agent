import 'package:flutter/material.dart';

/// Design tokens taken pixel-for-pixel from docs/assets/*.svg.
class AppColors {
  static const bg = Color(0xFFF8FAFC);
  static const headerTop = Color(0xFF0F172A);
  static const headerBottom = Color(0xFF1E293B);
  static const primary = Color(0xFF2563EB);

  static const card = Color(0xFFFFFFFF);
  static const cardBorder = Color(0xFFEAEEF3);
  static const divider = Color(0xFFE2E8F0);
  static const chevron = Color(0xFFCBD5E1);

  static const textTitle = Color(0xFF0F172A);   // headings, card titles
  static const textBody = Color(0xFF475569);     // body
  static const textBody2 = Color(0xFF334155);    // chat text
  static const textMuted = Color(0xFF64748B);    // sublabels
  static const textFaint = Color(0xFF94A3B8);    // meta, placeholders

  // "Next ->" strip
  static const nextStripBg = Color(0xFFEFF6FF);
  static const nextStripText = Color(0xFF1E40AF);
  static const nextStripEscalatedBg = Color(0xFFFEF2F2);
  static const nextStripEscalatedText = Color(0xFFB91C1C);

  // Safety warning bubble
  static const safetyBg = Color(0xFFFEF2F2);
  static const safetyText = Color(0xFF991B1B);

  // Chat bubbles
  static const userBubble = Color(0xFF2563EB);
  static const userBubbleText = Color(0xFFFFFFFF);
  static const agentBubbleBorder = Color(0xFFEAEEF3);

  // Escalate (outline) button
  static const escalateBorder = Color(0xFFFCA5A5);
  static const escalateText = Color(0xFFB91C1C);

  // Step checklist dots
  static const stepDone = Color(0xFF22C55E);     // green
  static const stepPending = Color(0xFFF59E0B);  // amber
}

/// One status' badge + accent palette. Used by the home cards and detail header.
class StatusStyle {
  final String label;        // e.g. "DIAGNOSING", "AWAITING YOU"
  final Color badgeBg;
  final Color dot;           // status dot + left accent bar
  final Color text;
  const StatusStyle(this.label, this.badgeBg, this.dot, this.text);

  static StatusStyle of(String status) {
    switch (status) {
      case 'intake':
        return const StatusStyle('INTAKE', Color(0xFFF1F5F9), Color(0xFF94A3B8), Color(0xFF475569));
      case 'diagnosing':
        return const StatusStyle('DIAGNOSING', Color(0xFFFEF3C7), Color(0xFFF59E0B), Color(0xFFB45309));
      case 'awaiting_user':
        return const StatusStyle('AWAITING YOU', Color(0xFFDBEAFE), Color(0xFF3B82F6), Color(0xFF1D4ED8));
      case 'escalated':
        return const StatusStyle('ESCALATED', Color(0xFFFEE2E2), Color(0xFFEF4444), Color(0xFFB91C1C));
      case 'resolved':
        return const StatusStyle('RESOLVED', Color(0xFFDCFCE7), Color(0xFF22C55E), Color(0xFF15803D));
      default:
        return const StatusStyle('OPEN', Color(0xFFF1F5F9), Color(0xFF94A3B8), Color(0xFF475569));
    }
  }
}

/// App-wide ThemeData. Uses the platform default font (close to the mockup's system font).
ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      primary: AppColors.primary,
      surface: AppColors.card,
    ),
    fontFamily: null,
  );
}
