import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import '../widgets/status_badge.dart';

class EscalationScreen extends StatefulWidget {
  final String caseId;
  final ApiClient? client;
  final Future<void> Function(String shareText)? onShare;
  final Future<void> Function(String recipient)? onContact;

  const EscalationScreen({
    super.key,
    required this.caseId,
    this.client,
    this.onShare,
    this.onContact,
  });

  @override
  State<EscalationScreen> createState() => _EscalationScreenState();
}

class _EscalationScreenState extends State<EscalationScreen> {
  late final ApiClient _api = widget.client ?? ApiClient();
  IssueDetail? _detail;
  Escalation? _escalation;
  final Set<int> _doneOrders = {};
  bool _loading = true;
  String? _error;
  bool _draftExpanded = false;

  static final _firstAlphaWord = RegExp(r'[A-Za-z]+');
  static const _diagnosisKeywords = [
    'airflow',
    'coils',
    'compressor',
    'relay',
    'defrost',
    'drain',
    'seal',
    'fan',
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      var detail = await _api.getIssue(widget.caseId);
      if (detail.escalation == null) {
        await _api.escalate(widget.caseId);
        detail = await _api.getIssue(widget.caseId);
      }
      final escalation = detail.escalation;
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _escalation = escalation;
        _loading = false;
        _error = escalation == null ? 'Escalation packet was not available.' : null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  List<EscalationStep> get _steps => _escalation?.escalationSteps ?? const [];

  int get _total => _steps.length;

  int get _done => _doneOrders.length;

  bool get _complete => _total > 0 && _done >= _total;

  Packet? get _packet => _escalation?.packet;

  String get _brand => _detail?.brand ?? 'Brand';

  String get _appliance => _detail?.appliance ?? 'Appliance';

  String get _model => _packet?.model ?? _detail?.modelNumber ?? 'model unknown';

  String get _caseId => _detail?.caseId ?? widget.caseId;

  void _toggleStep(int order) {
    setState(() {
      if (!_doneOrders.remove(order)) _doneOrders.add(order);
    });
  }

  Future<void> _share() async {
    final escalation = _escalation;
    final packet = _packet;
    if (escalation == null || packet == null) return;
    final shareText =
        '${escalation.draftedEmail}\n\n--\nService packet: model $_model, '
        '${packet.stepsTried} steps tried, $_total escalation step(s).';

    try {
      if (widget.onShare != null) {
        await widget.onShare!(shareText);
      } else {
        await Share.share(shareText);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Shared')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not share packet: $e')),
      );
    }
  }

  Future<void> _contact() async {
    final escalation = _escalation;
    if (escalation == null) return;
    final recipient = escalation.recipient;
    final phone = escalation.phone?.trim();

    try {
      if (widget.onContact != null) {
        await widget.onContact!(phone?.isNotEmpty == true ? phone! : recipient);
        return;
      }

      final uri = phone?.isNotEmpty == true
          ? Uri(scheme: 'tel', path: phone)
          : Uri(
              scheme: 'mailto',
              path: recipient,
              queryParameters: {'subject': 'Service request $_caseId'},
            );
      final launched = await launchUrl(uri);
      if (!mounted) return;
      if (!launched) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              phone?.isNotEmpty == true
                  ? 'Could not open phone app'
                  : 'Could not open email app',
            ),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not contact service: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Column(
        children: [
          const AppHeader(title: 'Service packet', showBack: true),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'Could not load service packet.\n$_error',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textMuted),
          ),
        ),
      );
    }
    final detail = _detail;
    final escalation = _escalation;
    if (detail == null || escalation == null || escalation.packet == null) {
      return const SizedBox.shrink();
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _subRow(detail),
        const SizedBox(height: 12),
        _progressBanner(),
        const SizedBox(height: 14),
        _packetContentsCard(detail, escalation.packet!),
        const SizedBox(height: 14),
        if (_steps.isNotEmpty) ...[
          _escalationStepsCard(),
          const SizedBox(height: 14),
        ],
        _primaryButton(),
        const SizedBox(height: 8),
        _secondaryButton(),
        const SizedBox(height: 8),
        Text(
          'Call or email ${String.fromCharCode(0x2014)} reach out now, or finish the steps first.',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 10.5, color: AppColors.textFaint),
        ),
        const SizedBox(height: 12),
        _draftedMessageSection(escalation.draftedEmail),
      ],
    );
  }

  Widget _subRow(IssueDetail detail) {
    final middot = String.fromCharCode(0x00B7);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                '$_brand $middot $_appliance',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textTitle,
                ),
              ),
            ),
            const SizedBox(width: 8),
            const StatusBadge(status: 'escalated'),
          ],
        ),
        const SizedBox(height: 3),
        Text(
          '$_model $middot ${detail.caseId}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 12, color: AppColors.textFaint),
        ),
      ],
    );
  }

  Widget _progressBanner() {
    final remaining = (_total - _done).clamp(0, _total);
    final value = _total == 0 ? 1.0 : (_done / _total).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.nextStripBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFBFDBFE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _complete ? 'Steps complete.' : 'Before a technician visit...',
            style: const TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              color: AppColors.nextStripText,
            ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: value,
              minHeight: 6,
              backgroundColor: const Color(0xFFDBEAFE),
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _complete
                ? 'All steps done ${String.fromCharCode(0x2014)} share the packet or contact support.'
                : 'Work through $remaining escalation step(s) below, then share.',
            style: const TextStyle(
              fontSize: 10.5,
              color: AppColors.nextStripText,
            ),
          ),
        ],
      ),
    );
  }

  Widget _packetContentsCard(IssueDetail detail, Packet packet) {
    final middot = String.fromCharCode(0x00B7);
    return _card(
      borderColor: AppColors.cardBorder,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Packet contents',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppColors.textTitle,
            ),
          ),
          const SizedBox(height: 13),
          _contentRow(
            _checkMark(),
            'Appliance & model',
            '$_brand $middot $_model',
          ),
          const SizedBox(height: 10),
          _contentRow(
            _checkMark(),
            'Problem & diagnosis',
            _problemTag(detail),
          ),
          const SizedBox(height: 10),
          _contentRow(
            _checkMark(),
            'Steps already tried',
            '${packet.stepsTried} logged',
          ),
          const SizedBox(height: 10),
          _contentRow(
            _complete ? _checkMark() : _pendingDot(),
            'Escalation steps',
            '$_done of $_total done',
            valueColor: _complete ? AppColors.stepDone : const Color(0xFFB45309),
            strong: true,
          ),
        ],
      ),
    );
  }

  Widget _contentRow(
    Widget leading,
    String label,
    String value, {
    Color? valueColor,
    bool strong = false,
  }) {
    return Row(
      children: [
        SizedBox(width: 20, height: 20, child: Center(child: leading)),
        const SizedBox(width: 10),
        Text(
          label,
          style: TextStyle(
            fontSize: 12.5,
            color: AppColors.textBody,
            fontWeight: strong ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
        const Spacer(),
        Flexible(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.right,
            style: TextStyle(
              fontSize: 11,
              color: valueColor ?? AppColors.textFaint,
              fontWeight: strong ? FontWeight.w700 : FontWeight.w400,
            ),
          ),
        ),
      ],
    );
  }

  Widget _escalationStepsCard() {
    final middot = String.fromCharCode(0x00B7);
    final rows = <Widget>[];
    for (var i = 0; i < _steps.length; i++) {
      if (i > 0) rows.add(const SizedBox(height: 12));
      rows.add(_stepRow(_steps[i]));
    }
    return _card(
      borderColor: const Color(0xFFBFDBFE),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'NOW $middot ESCALATION STEPS',
                style: const TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                  color: AppColors.primary,
                ),
              ),
              const Spacer(),
              Text(
                '$_done of $_total',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'When you call, support will walk you through these same checks. '
            'Doing them first means you will be more prepared, and may even fix '
            'the issue before you reach anyone.',
            style: TextStyle(
              fontSize: 10.5,
              height: 1.4,
              color: AppColors.textMuted,
            ),
          ),
          const SizedBox(height: 12),
          ...rows,
        ],
      ),
    );
  }

  Widget _stepRow(EscalationStep step) {
    final done = _doneOrders.contains(step.order);
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () => _toggleStep(step.order),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 22,
              height: 22,
              child: Center(child: done ? _checkMark() : _emptyRing()),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.instruction,
                    style: TextStyle(
                      fontSize: 12.5,
                      height: 1.35,
                      color: done ? AppColors.textFaint : AppColors.textBody,
                      decoration:
                          done ? TextDecoration.lineThrough : TextDecoration.none,
                    ),
                  ),
                  const SizedBox(height: 5),
                  _kindChip(step.kind),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _kindChip(String kind) {
    const labels = {
      'check': 'CHECK',
      'action': 'DO',
      'wait': 'WAIT',
      'call': 'CALL',
    };
    final label = labels[kind] ?? kind.toUpperCase();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.nextStripBg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFBFDBFE)),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 8.5,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.4,
          color: AppColors.primary,
        ),
      ),
    );
  }

  Widget _primaryButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: ElevatedButton(
        onPressed: _contact,
        style: ElevatedButton.styleFrom(
          elevation: 0,
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
        child: Text('Contact $_brand'),
      ),
    );
  }

  Widget _secondaryButton() {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: OutlinedButton(
        onPressed: _share,
        style: OutlinedButton.styleFrom(
          backgroundColor: AppColors.card,
          foregroundColor: AppColors.textBody2,
          side: const BorderSide(color: AppColors.chevron),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
        child: const Text('Share service packet'),
      ),
    );
  }

  Widget _draftedMessageSection(String draftedEmail) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => setState(() => _draftExpanded = !_draftExpanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Drafted message',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textTitle,
                      ),
                    ),
                  ),
                  Icon(
                    _draftExpanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    color: AppColors.textMuted,
                    size: 20,
                  ),
                ],
              ),
            ),
          ),
          if (_draftExpanded)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.bg,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.cardBorder),
              ),
              child: Text(
                draftedEmail,
                style: const TextStyle(
                  fontSize: 12,
                  height: 1.35,
                  color: AppColors.textBody,
                  fontFamily: 'monospace',
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _card({required Color borderColor, required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }

  Widget _checkMark() {
    return const Icon(Icons.check_circle, color: AppColors.stepDone, size: 20);
  }

  Widget _pendingDot() {
    return Container(
      width: 16,
      height: 16,
      decoration: const BoxDecoration(
        color: AppColors.stepPending,
        shape: BoxShape.circle,
      ),
    );
  }

  Widget _emptyRing() {
    return const Icon(
      Icons.radio_button_unchecked,
      color: AppColors.chevron,
      size: 20,
    );
  }

  String _problemTag(IssueDetail detail) {
    final symptomWord = _firstAlphaWord
            .firstMatch(detail.symptom)
            ?.group(0)
            ?.toLowerCase() ??
        'issue';
    final diagnosis = detail.diagnosis?.hypothesis ?? '';
    final diagnosisLower = diagnosis.toLowerCase();
    final keyword = _diagnosisKeywords.firstWhere(
      diagnosisLower.contains,
      orElse: () =>
          _firstAlphaWord.firstMatch(diagnosis)?.group(0)?.toLowerCase() ??
          'diagnosis',
    );
    return '$symptomWord ${String.fromCharCode(0x00B7)} $keyword';
  }
}
