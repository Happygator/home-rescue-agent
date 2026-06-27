import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../models.dart';
import '../services/media_capture.dart';
import '../services/upload.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import '../widgets/case_summary_card.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/status_badge.dart';
import 'escalation_screen.dart';

class IssueDetailScreen extends StatefulWidget {
  final String caseId;
  final ApiClient? client;
  final MediaCapture? capture;
  const IssueDetailScreen({super.key, required this.caseId, this.client, this.capture});

  @override
  State<IssueDetailScreen> createState() => _IssueDetailScreenState();
}

class _IssueDetailScreenState extends State<IssueDetailScreen> {
  late final ApiClient _api = widget.client ?? ApiClient();
  final _scroll = ScrollController();
  final _text = TextEditingController();
  IssueDetail? _detail;
  final List<ChatMessage> _messages = [];
  bool _loading = true;
  bool _kickedOff = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final detail = await _api.getIssue(widget.caseId);
      if (!mounted) return;
      setState(() {
        _detail = detail;
        _messages
          ..clear()
          ..addAll(_buildTranscript(detail));
        _loading = false;
        _error = null;
      });
      _scrollToBottom();
      // Auto-kickoff: a fresh intake case with a symptom gets Gemini's first fix immediately
      // instead of waiting for the user to type. Fires at most once per screen.
      if (!_kickedOff && detail.status == 'intake' && detail.symptom.trim().isNotEmpty) {
        _kickedOff = true;
        _kickoff();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _kickoff() async {
    final agent = ChatMessage(ChatRole.agent, '');
    setState(() => _messages.add(agent));
    _scrollToBottom();
    var gotToken = false;
    try {
      await for (final ev in _api.streamStart(widget.caseId)) {
        if (ev.type == 'token') {
          final token = ev.text ?? '';
          if (token.isNotEmpty) {
            gotToken = true;
            _appendToken(agent, token);
          }
          if (!mounted) return;
          setState(() {});
          _scrollToBottom();
        }
      }
    } catch (_) {
      // Leave whatever streamed; the user can keep typing to continue.
    }
    if (!mounted) return;
    if (!gotToken) {
      // Nothing streamed (e.g. already started server-side) -> drop the empty bubble.
      setState(() => _messages.remove(agent));
    }
    // Refresh so the status badge + next-step strip reflect the started diagnosis.
    try {
      final refreshed = await _api.getIssue(widget.caseId);
      if (!mounted) return;
      setState(() => _detail = refreshed);
    } catch (_) {}
  }

  // Prefer the persisted server-side transcript so chat history survives reopen. Only when a
  // case has no stored messages (e.g. legacy/seeded demo cases) do we synthesize one from steps.
  List<ChatMessage> _buildTranscript(IssueDetail detail) {
    if (detail.messages.isNotEmpty) {
      return detail.messages.map((m) {
        final role = m.role == 'user'
            ? ChatRole.user
            : m.role == 'safety'
                ? ChatRole.safety
                : ChatRole.agent;
        return ChatMessage(
          role,
          m.text,
          imageUrl: m.mediaRef == null ? null : _api.mediaUrl(widget.caseId, m.mediaRef!),
          sentAtLabel: m.mediaRef == null ? null : _tsLabel(m.ts),
        );
      }).toList();
    }
    return _seedTranscript(detail);
  }

  void _appendToken(ChatMessage message, String token) {
    // Tokens are word-chunks; join with a space so live replies read the same as the
    // persisted transcript, which the server joins with single spaces.
    message.text = message.text.isEmpty ? token : '${message.text} $token';
  }

  List<ChatMessage> _seedTranscript(IssueDetail detail) {
    final target = detail.brand == null
        ? 'your appliance'
        : 'your ${detail.brand} ${detail.appliance ?? 'appliance'}';
    final seeded = <ChatMessage>[
      ChatMessage(ChatRole.agent, "I'm picking up where we left off on $target."),
    ];

    for (final step in detail.steps) {
      seeded.add(ChatMessage(ChatRole.agent, "Let's try: ${step.instruction}."));
      if (step.userResult != null && step.userResult!.isNotEmpty) {
        seeded.add(ChatMessage(ChatRole.user, step.userResult!));
      }
    }

    if (detail.nextStep.isNotEmpty) {
      seeded.add(ChatMessage(ChatRole.agent, detail.nextStep));
    }

    if (_needsSafetyCaveat(detail)) {
      final endash = String.fromCharCode(0x2014);
      seeded.add(ChatMessage(ChatRole.safety, "I won't advise sealed-system or mains-voltage work $endash that needs a pro."));
    }

    return seeded;
  }

  bool _needsSafetyCaveat(IssueDetail detail) {
    final haystack = [
      detail.symptom,
      detail.diagnosis?.hypothesis ?? '',
      detail.nextStep,
    ].join(' ').toLowerCase();
    return [
      'sealed',
      'compressor',
      'refrigerant',
      'evaporator',
      'mains',
      'voltage',
      'electrical',
      'relay',
    ].any(haystack.contains);
  }

  Future<void> _escalate() async {
    await _api.escalate(widget.caseId);
    if (!mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => EscalationScreen(caseId: widget.caseId)));
  }

  // Re-pull the case after an agent turn so the status badge, next-step, and the
  // escalation hand-off (which only appears once status == 'escalated') reflect any
  // status change the agent just made via its tools.
  Future<void> _refreshDetail() async {
    try {
      final refreshed = await _api.getIssue(widget.caseId);
      if (!mounted) return;
      setState(() => _detail = refreshed);
    } catch (_) {}
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    _text.clear();
    final agent = ChatMessage(ChatRole.agent, '');
    setState(() {
      _messages
        ..add(ChatMessage(ChatRole.user, text))
        ..add(agent);
    });
    _scrollToBottom();

    try {
      await for (final ev in _api.streamMessage(widget.caseId, text)) {
        if (ev.type == 'token') {
          final token = ev.text ?? '';
          if (token.isNotEmpty) {
            _appendToken(agent, token);
          }
          if (!mounted) return;
          setState(() {});
          _scrollToBottom();
        }
      }
    } catch (e) {
      agent.text += 'Could not stream a reply. Please try again.';
      if (!mounted) return;
      setState(() {});
      _scrollToBottom();
    }
    await _refreshDetail();
  }

  Future<void> _captureSymptomPhoto() async {
    final bytes = await (widget.capture ?? MediaCapture()).capturePhoto();
    if (!mounted) return;
    if (bytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Camera unavailable - you can describe it instead.')),
      );
      return;
    }

    String ref;
    try {
      ref = await uploadMediaWithRetry(
        _api,
        widget.caseId,
        bytes,
        filename: 'symptom.jpg',
        kind: 'symptom',
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Upload failed, will retry')),
      );
      return;
    }

    if (!mounted) return;
    final agent = ChatMessage(ChatRole.agent, '');
    setState(() {
      _messages
        ..add(ChatMessage(
          ChatRole.user,
          '',
          imageUrl: _api.mediaUrl(widget.caseId, ref),
          sentAtLabel: _clockLabel(TimeOfDay.now()),
        ))
        ..add(agent);
    });
    _scrollToBottom();

    // Actually run an agent turn on the photo so the user gets the read/assessment back,
    // instead of a dead "looking at it now" message that never resolves.
    try {
      await for (final ev in _api.streamMessage(widget.caseId, '', mediaRef: ref)) {
        if (ev.type == 'token') {
          final token = ev.text ?? '';
          if (token.isNotEmpty) {
            _appendToken(agent, token);
          }
          if (!mounted) return;
          setState(() {});
          _scrollToBottom();
        }
      }
      if (agent.text.isEmpty) {
        agent.text = 'Got your photo, but could not read anything from it.';
        if (!mounted) return;
        setState(() {});
        _scrollToBottom();
      }
    } catch (_) {
      if (agent.text.isEmpty) {
        agent.text = 'Got your photo, but I could not analyze it. Please try again.';
      }
      if (!mounted) return;
      setState(() {});
      _scrollToBottom();
    }
    await _refreshDetail();
  }

  // Format a wall-clock label like "10:34 AM" without needing localization context.
  String _clockLabel(TimeOfDay t) {
    final hour = t.hourOfPeriod == 0 ? 12 : t.hourOfPeriod;
    final minute = t.minute.toString().padLeft(2, '0');
    final period = t.period == DayPeriod.am ? 'AM' : 'PM';
    return '$hour:$minute $period';
  }

  // Parse a persisted ISO timestamp into a short local clock label, or null if absent/unparseable.
  String? _tsLabel(String? iso) {
    if (iso == null || iso.isEmpty) return null;
    final dt = DateTime.tryParse(iso);
    if (dt == null) return null;
    return _clockLabel(TimeOfDay.fromDateTime(dt.toLocal()));
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      backgroundColor: AppColors.bg,
      resizeToAvoidBottomInset: true,
      body: Column(
        children: [
          AppHeader(title: detail?.displayTitle ?? 'Issue', showBack: true),
          if (detail != null) _subRow(detail),
          if (detail != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
              child: CaseSummaryCard(detail: detail, onEscalate: () { _escalate(); }),
            ),
          Expanded(child: _body()),
          if (detail != null) _inputBar(),
        ],
      ),
    );
  }

  Widget _body() {
    final detail = _detail;
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text('Could not load issue.\n$_error',
              textAlign: TextAlign.center, style: const TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    if (detail == null) {
      return const SizedBox.shrink();
    }
    return ListView(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      children: [
        ..._messages.map((m) => ChatBubble(message: m)),
        if (detail.status == 'escalated') _escalationCta(),
        const SizedBox(height: 8),
      ],
    );
  }

  // Shown once the agent has escalated: an explicit hand-off into the service-packet
  // (escalation info-gathering) screen, where the user reviews the drafted message,
  // captures the guided inspection shots, and shares or contacts the pro.
  Widget _escalationCta() {
    return Padding(
      padding: const EdgeInsets.only(top: 6, bottom: 4),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.nextStripBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFBFDBFE)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Ready for a professional',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.nextStripText),
            ),
            const SizedBox(height: 4),
            const Text(
              'Set up the service packet: review the drafted message, capture a quick inspection video, and contact the pro.',
              style: TextStyle(fontSize: 12, height: 1.35, color: AppColors.nextStripText),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 44,
              child: ElevatedButton(
                onPressed: _escalate,
                style: ElevatedButton.styleFrom(
                  elevation: 0,
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  textStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
                ),
                child: Text('Set up professional service  ${String.fromCharCode(0x2192)}'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _subRow(IssueDetail detail) {
    final middot = String.fromCharCode(0x00B7);
    final model = detail.modelNumber ?? detail.appliance ?? 'Appliance';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Flexible(
            child: Text('$model $middot ${detail.caseId}',
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
          ),
          const SizedBox(width: 8),
          StatusBadge(status: detail.status),
        ],
      ),
    );
  }

  Widget _inputBar() {
    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.bg,
          border: Border(top: BorderSide(color: AppColors.divider)),
        ),
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _text,
                minLines: 1,
                maxLines: 4,
                decoration: InputDecoration(
                  hintText: 'Type a reply...',
                  hintStyle: const TextStyle(color: AppColors.textFaint),
                  filled: true,
                  fillColor: AppColors.card,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: AppColors.divider),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: AppColors.divider),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 44,
              height: 44,
              child: IconButton(
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.card,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _captureSymptomPhoto,
                icon: const Icon(Icons.photo_camera_outlined, color: AppColors.textBody),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 40,
              height: 40,
              child: IconButton(
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  shape: const CircleBorder(),
                ),
                onPressed: _send,
                icon: const Icon(Icons.send, color: Colors.white, size: 18),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
