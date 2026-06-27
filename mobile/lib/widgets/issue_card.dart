import 'package:flutter/material.dart';
import '../models.dart';
import '../theme.dart';
import '../utils/relative_time.dart';
import 'status_badge.dart';
import 'next_strip.dart';

class IssueCard extends StatelessWidget {
  final IssueSummary issue;
  final VoidCallback? onTap;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;
  const IssueCard({super.key, required this.issue, this.onTap, this.onEdit, this.onDelete});

  static const Color _danger = Color(0xFFB91C1C);

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
          child: Stack(
            children: [
              Positioned(
                left: 0,
                top: 14,
                bottom: 14,
                width: 4,
                child: DecoratedBox(decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(2))),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 14, 6, 14),
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
                        if (onEdit != null || onDelete != null) _menu(),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: Text(meta, style: const TextStyle(fontSize: 11.5, color: AppColors.textFaint)),
                    ),
                    const SizedBox(height: 10),
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: Text(issue.symptom, maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.5, color: AppColors.textBody)),
                    ),
                    if (issue.nextStep.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: NextStrip(text: issue.nextStep, escalated: issue.status == 'escalated'),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _menu() {
    return PopupMenuButton<String>(
      tooltip: 'Ticket options',
      icon: const Icon(Icons.more_vert, size: 20, color: AppColors.textFaint),
      padding: EdgeInsets.zero,
      splashRadius: 20,
      position: PopupMenuPosition.under,
      onSelected: (value) {
        if (value == 'edit') onEdit?.call();
        if (value == 'delete') onDelete?.call();
      },
      itemBuilder: (context) => [
        if (onEdit != null)
          const PopupMenuItem<String>(
            value: 'edit',
            child: Row(
              children: [
                Icon(Icons.edit_outlined, size: 18, color: AppColors.textBody),
                SizedBox(width: 10),
                Text('Edit details'),
              ],
            ),
          ),
        if (onDelete != null)
          const PopupMenuItem<String>(
            value: 'delete',
            child: Row(
              children: [
                Icon(Icons.delete_outline, size: 18, color: _danger),
                SizedBox(width: 10),
                Text('Delete', style: TextStyle(color: _danger)),
              ],
            ),
          ),
      ],
    );
  }
}
