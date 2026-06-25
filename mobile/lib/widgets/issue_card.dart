import 'package:flutter/material.dart';
import '../models.dart';
import '../theme.dart';
import '../utils/relative_time.dart';
import 'status_badge.dart';
import 'next_strip.dart';

class IssueCard extends StatelessWidget {
  final IssueSummary issue;
  final VoidCallback? onTap;
  const IssueCard({super.key, required this.issue, this.onTap});

  @override
  Widget build(BuildContext context) {
    final accent = StatusStyle.of(issue.status).dot;
    final meta = issue.modelNumber != null && issue.modelNumber!.isNotEmpty
        ? '${issue.modelNumber} ${String.fromCharCode(0x00B7)} updated ${relativeTime(issue.updatedAt)}'
        : 'updated ${relativeTime(issue.updatedAt)}';
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.cardBorder),
        boxShadow: const [BoxShadow(color: Color(0x140F172A), offset: Offset(0, 2), blurRadius: 6)],
      ),
      clipBehavior: Clip.antiAlias,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Container(width: 4, decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(2))),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(issue.displayTitle, maxLines: 1, overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: AppColors.textTitle))),
                            const SizedBox(width: 8),
                            StatusBadge(status: issue.status),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(meta, style: const TextStyle(fontSize: 11.5, color: AppColors.textFaint)),
                        const SizedBox(height: 10),
                        Text(issue.symptom, maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12.5, color: AppColors.textBody)),
                        if (issue.nextStep.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          NextStrip(text: issue.nextStep, escalated: issue.status == 'escalated'),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
