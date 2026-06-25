import 'package:flutter/material.dart';
import '../theme.dart';

class StatusBadge extends StatelessWidget {
  final String status;
  const StatusBadge({super.key, required this.status});
  @override
  Widget build(BuildContext context) {
    final s = StatusStyle.of(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: s.badgeBg, borderRadius: BorderRadius.circular(11)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 6, height: 6, decoration: BoxDecoration(color: s.dot, shape: BoxShape.circle)),
          const SizedBox(width: 7),
          Text(s.label, style: TextStyle(color: s.text, fontWeight: FontWeight.w700, fontSize: 11, letterSpacing: 0.2)),
        ],
      ),
    );
  }
}
