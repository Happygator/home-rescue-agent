import 'package:flutter/material.dart';
import '../models.dart';
import '../theme.dart';
import 'next_strip.dart';

class CaseSummaryCard extends StatefulWidget {
  final IssueDetail detail;
  final VoidCallback onEscalate;
  const CaseSummaryCard({super.key, required this.detail, required this.onEscalate});
  @override
  State<CaseSummaryCard> createState() => _CaseSummaryCardState();
}

class _CaseSummaryCardState extends State<CaseSummaryCard> {
  bool _expanded = true;

  // Brand + model (whichever are known) for the summary's Model line; the no-brand compact
  // fridge shows just the model code, and a not-yet-identified case reads clearly.
  String _modelText(IssueDetail d) {
    final parts = [d.brand, d.modelNumber]
        .where((s) => s != null && s.trim().isNotEmpty)
        .cast<String>()
        .toList();
    return parts.isEmpty ? 'not identified yet' : parts.join(' ${String.fromCharCode(0x00b7)} ');
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.detail;
    final endash = String.fromCharCode(0x2014);
    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.cardBorder),
            boxShadow: const [BoxShadow(color: Color(0x140F172A), offset: Offset(0, 2), blurRadius: 6)],
          ),
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              GestureDetector(
                onTap: () => setState(() => _expanded = !_expanded),
                behavior: HitTestBehavior.opaque,
                child: Row(
                  children: [
                    const Text('Case summary', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.textTitle)),
                    const Spacer(),
                    Icon(_expanded ? Icons.expand_less : Icons.expand_more, size: 20, color: AppColors.textFaint),
                  ],
                ),
              ),
              if (_expanded) ...[
                const SizedBox(height: 10),
                Text('Model: ${_modelText(d)}', style: const TextStyle(fontSize: 12.5, color: AppColors.textBody)),
                const SizedBox(height: 6),
                Text('Symptom: ${d.symptom}', style: const TextStyle(fontSize: 12.5, color: AppColors.textBody)),
                if (d.diagnosis != null) ...[
                  const SizedBox(height: 6),
                  Text('Diagnosis: ${d.diagnosis!.hypothesis}', style: const TextStyle(fontSize: 12.5, color: AppColors.textBody)),
                ],
                const SizedBox(height: 10),
                ...d.steps.map((s) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Container(width: 8, height: 8, decoration: BoxDecoration(
                                color: s.isDone ? AppColors.stepDone : AppColors.stepPending, shape: BoxShape.circle)),
                          ),
                          const SizedBox(width: 12),
                          Expanded(child: Text('${s.instruction} $endash ${s.userResult ?? 'pending'}',
                              style: const TextStyle(fontSize: 12, color: AppColors.textBody))),
                        ],
                      ),
                    )),
                if (d.nextStep.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  const Divider(height: 16, thickness: 1, color: AppColors.divider),
                  NextStrip(text: d.nextStep, escalated: d.status == 'escalated'),
                ],
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          height: 44,
          child: OutlinedButton(
            onPressed: widget.onEscalate,
            style: OutlinedButton.styleFrom(
              backgroundColor: AppColors.card,
              side: const BorderSide(color: AppColors.escalateBorder),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: const Text('Escalate to a pro', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.escalateText)),
          ),
        ),
      ],
    );
  }
}
