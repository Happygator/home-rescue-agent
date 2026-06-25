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
  int _captured = 0;
  int _total = 0;
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
      final packet = escalation?.packet;
      final guideTotal = escalation?.inspectionGuide.length ?? 0;
      final total = packet == null || packet.shotsTotal == 0
          ? guideTotal
          : packet.shotsTotal;
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _escalation = escalation;
        _captured = packet?.shotsCaptured ?? 0;
        _total = total;
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

  InspectionShot? get _currentShot {
    final guide = _escalation?.inspectionGuide;
    if (guide == null || _captured >= guide.length) return null;
    return guide[_captured];
  }

  Packet? get _packet => _escalation?.packet;

  String get _brand => _detail?.brand ?? 'Brand';

  String get _appliance => _detail?.appliance ?? 'Appliance';

  String get _model => _packet?.model ?? _detail?.modelNumber ?? 'model unknown';

  String get _caseId => _detail?.caseId ?? widget.caseId;

  bool get _complete => _total == 0 || _captured >= _total;

  void _capture() {
    setState(() {
      if (_captured < _total) _captured++;
    });
  }

  Future<void> _share() async {
    final escalation = _escalation;
    final packet = _packet;
    if (escalation == null || packet == null) return;
    final shareText =
        '${escalation.draftedEmail}\n\n--\nService packet: model $_model, '
        '${packet.stepsTried} steps tried, $_total inspection shots.';

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

    try {
      if (widget.onContact != null) {
        await widget.onContact!(recipient);
        return;
      }
      final uri = Uri.parse(
        'mailto:$recipient?subject=${Uri.encodeComponent('Service request $_caseId')}',
      );
      final launched = await launchUrl(uri);
      if (!mounted) return;
      if (!launched) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open email app')),
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

    final shot = _currentShot;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _subRow(detail),
        const SizedBox(height: 12),
        _progressBanner(),
        const SizedBox(height: 14),
        _packetContentsCard(detail, escalation.packet!),
        const SizedBox(height: 14),
        if (!_complete && shot != null) ...[
          _guidedVideoCard(shot),
          const SizedBox(height: 14),
        ],
        _primaryButton(),
        const SizedBox(height: 8),
        _secondaryButton(),
        const SizedBox(height: 8),
        Text(
          'Call or email ${String.fromCharCode(0x2014)} reach out now, or finish the packet first.',
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
    final remaining = (_total - _captured).clamp(0, _total);
    final value = _total == 0 ? 1.0 : (_captured / _total).clamp(0.0, 1.0);
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
            _complete ? 'Packet ready to share.' : 'Preparing your packet...',
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
                ? 'All shots captured ${String.fromCharCode(0x2014)} review and share.'
                : 'Almost there ${String.fromCharCode(0x2014)} $remaining guided inspection shot(s) to go.',
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
    final warranty = packet.warrantyStatus;
    final warrantyNeedsCheck =
        warranty == null || warranty.toLowerCase().contains('check');
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
            'Inspection video',
            _complete ? '$_total of $_total shots' : '$_captured of $_total shots',
            valueColor: _complete ? AppColors.stepDone : const Color(0xFFB45309),
            strong: true,
          ),
          const SizedBox(height: 10),
          _contentRow(
            warrantyNeedsCheck ? _emptyRing() : _checkMark(),
            'Warranty status',
            warranty ?? 'checking...',
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

  Widget _guidedVideoCard(InspectionShot shot) {
    final middot = String.fromCharCode(0x00B7);
    return _card(
      borderColor: const Color(0xFFBFDBFE),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'NOW $middot GUIDED VIDEO',
                style: const TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w700,
                  color: AppColors.primary,
                ),
              ),
              const Spacer(),
              Text(
                'Shot ${_captured + 1} of $_total',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            height: 120,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.headerTop,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Stack(
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: const BoxDecoration(
                        color: Color(0xFFEF4444),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'REC 0:00',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.9),
                        fontSize: 9.5,
                      ),
                    ),
                  ],
                ),
                Center(
                  child: Container(
                    width: 150,
                    height: 76,
                    alignment: Alignment.center,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.24),
                        width: 1.2,
                      ),
                    ),
                    child: Text(
                      shot.whatToFilm,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.85),
                        fontSize: 11,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            shot.narration,
            style: const TextStyle(fontSize: 11, color: AppColors.textBody),
          ),
        ],
      ),
    );
  }

  Widget _primaryButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: ElevatedButton(
        onPressed: _complete ? _share : _capture,
        style: ElevatedButton.styleFrom(
          elevation: 0,
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
        child: Text(_complete ? 'Share service packet' : 'Capture this shot'),
      ),
    );
  }

  Widget _secondaryButton() {
    return SizedBox(
      width: double.infinity,
      height: 44,
      child: OutlinedButton(
        onPressed: _contact,
        style: OutlinedButton.styleFrom(
          backgroundColor: AppColors.card,
          foregroundColor: AppColors.textBody2,
          side: const BorderSide(color: AppColors.chevron),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
        child: Text('Contact $_brand'),
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
    return const Icon(Icons.check, color: AppColors.stepDone, size: 20);
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
