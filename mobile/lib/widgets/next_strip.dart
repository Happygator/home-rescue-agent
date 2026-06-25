import 'package:flutter/material.dart';
import '../theme.dart';

class NextStrip extends StatelessWidget {
  final String text;
  final bool escalated;
  const NextStrip({super.key, required this.text, this.escalated = false});
  @override
  Widget build(BuildContext context) {
    final bg = escalated ? AppColors.nextStripEscalatedBg : AppColors.nextStripBg;
    final fg = escalated ? AppColors.nextStripEscalatedText : AppColors.nextStripText;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
      child: RichText(
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        text: TextSpan(
          style: TextStyle(color: fg, fontSize: 12, height: 1.35),
          children: [
            TextSpan(text: 'Next ${String.fromCharCode(0x2192)} ', style: const TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(text: text),
          ],
        ),
      ),
    );
  }
}
