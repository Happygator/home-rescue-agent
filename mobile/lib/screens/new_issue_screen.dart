import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../services/media_capture.dart';
import '../services/upload.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/next_strip.dart';
import 'issue_detail_screen.dart';

class NewIssueScreen extends StatefulWidget {
  final ApiClient? client;

  // Injectable capture: returns plate image bytes, or null if the user/camera denied.
  // Default uses the device camera; tests can override it.
  final Future<List<int>?> Function()? capturePlate;

  const NewIssueScreen({super.key, this.client, this.capturePlate});

  @override
  State<NewIssueScreen> createState() => _NewIssueScreenState();
}

class _NewIssueScreenState extends State<NewIssueScreen> {
  late final ApiClient _api = widget.client ?? ApiClient();
  final _text = TextEditingController();
  final _manualModel = TextEditingController();
  final _messages = <ChatMessage>[];

  String? _caseId;
  String? _appliance = 'Refrigerator';
  String? _brand;
  String? _model;
  String? _symptom;
  String? _errorCode;
  bool _manualEntry = false;
  bool _starting = true;
  bool _scanning = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    _text.dispose();
    _manualModel.dispose();
    super.dispose();
  }

  Future<void> _init() async {
    setState(() {
      _starting = true;
      _error = null;
    });

    try {
      final caseId = await _api.createIssue(appliance: 'Refrigerator');
      if (!mounted) return;
      setState(() {
        _caseId = caseId;
        _starting = false;
        _messages
          ..clear()
          ..addAll([
            ChatMessage(ChatRole.agent, "Hi! I'm your Appliance Fixer assistant."),
            ChatMessage(
              ChatRole.agent,
              "Let's set up your issue. To start, tell me:\n"
              "1) What appliance is it (e.g. refrigerator)?\n"
              "2) What's it doing wrong?\n"
              "3) The model number on the spec plate.",
            ),
            ChatMessage(ChatRole.agent, 'Or tap the camera to scan the plate and auto-fill.'),
          ]);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _starting = false;
        _error = e.toString();
      });
    }
  }

  Future<List<int>?> _defaultCapture() => MediaCapture().capturePhoto();

  Future<void> _handlePlateBytes(List<int> bytes) async {
    final ref = await uploadMediaWithRetry(
      _api,
      _caseId!,
      bytes,
      filename: 'plate.jpg',
      kind: 'plate',
      mime: 'image/jpeg',
    );
    final plate = await _api.readPlate(_caseId!, mediaRef: ref);
    if (!mounted) return;
    setState(() {
      _brand = plate.brand ?? _brand;
      _model = plate.model ?? _model;
      _errorCode = plate.errorCode ?? _errorCode;
      _manualEntry = false;
      _scanning = false;
      final brand = _brand ?? 'Unknown brand';
      final model = _model ?? 'unknown model';
      _messages.add(ChatMessage(ChatRole.agent, 'Scanned your plate: $brand $model. Is that right? You can edit it.'));
    });
  }

  Future<void> _scanPlate() async {
    if (_caseId == null || _scanning) return;
    setState(() {
      _scanning = true;
      _error = null;
    });

    try {
      final bytes = await (widget.capturePlate ?? _defaultCapture)();
      if (!mounted) return;
      if (bytes == null) {
        setState(() {
          _manualEntry = true;
          _scanning = false;
          _messages.add(ChatMessage(ChatRole.agent, 'No problem - type your model number below instead.'));
        });
        return;
      }

      await _handlePlateBytes(bytes);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _scanning = false;
        _manualEntry = true;
        _error = e.toString();
        _messages.add(ChatMessage(ChatRole.agent, 'I could not scan the plate. Type your model number below instead.'));
      });
    }
  }

  Future<void> _choosePlatePhoto() async {
    if (_caseId == null || _scanning) return;
    setState(() {
      _scanning = true;
      _error = null;
    });

    try {
      final bytes = await MediaCapture().pickFromGallery();
      if (!mounted) return;
      if (bytes == null) {
        setState(() {
          _scanning = false;
        });
        return;
      }
      await _handlePlateBytes(bytes);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _scanning = false;
        _manualEntry = true;
        _error = e.toString();
        _messages.add(ChatMessage(ChatRole.agent, 'I could not scan the plate. Type your model number below instead.'));
      });
    }
  }

  void _send() {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    _text.clear();
    setState(() {
      _symptom ??= text;
      _messages
        ..add(ChatMessage(ChatRole.user, text))
        ..add(ChatMessage(ChatRole.agent, "Got it. I'll start diagnosing once we have the model and symptom."));
    });
  }

  void _startDiagnosis() {
    if (_caseId == null) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => IssueDetailScreen(caseId: _caseId!)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canStart = _model != null && _symptom != null;
    return Scaffold(
      backgroundColor: AppColors.bg,
      resizeToAvoidBottomInset: true,
      body: Column(
        children: [
          const AppHeader(title: 'New Issue', showBack: true),
          _statusRow(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _summaryCard(),
                if (_manualEntry) ...[
                  const SizedBox(height: 10),
                  _manualModelField(),
                ],
                const SizedBox(height: 14),
                if (_starting) _startingState(),
                if (_error != null && _caseId == null) _startError(),
                ..._messages.map((m) => ChatBubble(message: m)),
                if (_scanning)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: Text('Scanning plate...', style: TextStyle(color: AppColors.textFaint, fontSize: 12)),
                  ),
                if (_error != null && _caseId != null) _inlineError(),
                if (canStart) ...[
                  const SizedBox(height: 4),
                  _startButton(),
                ],
              ],
            ),
          ),
          _inputBar(),
        ],
      ),
    );
  }

  Widget _statusRow() {
    final status = StatusStyle.of('intake');
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
            decoration: BoxDecoration(
              color: status.badgeBg,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(color: status.dot, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(
                  status.label,
                  style: TextStyle(color: status.text, fontSize: 11, fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Gathering appliance details...',
              style: TextStyle(color: AppColors.textFaint, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.cardBorder),
        boxShadow: [
          const BoxShadow(
            color: Color(0x0A000000),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Case summary',
            style: TextStyle(color: AppColors.textTitle, fontSize: 13, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          _summaryRow('Appliance', _appliance, 'not specified yet'),
          const SizedBox(height: 6),
          _summaryRow('Symptom', _symptom, 'not described yet'),
          const SizedBox(height: 6),
          _summaryRow('Model', _model, 'awaiting spec plate'),
          const SizedBox(height: 12),
          const NextStrip(text: 'Answer below to start diagnosis.'),
        ],
      ),
    );
  }

  Widget _summaryRow(String label, String? value, String placeholder) {
    final hasValue = value != null && value.trim().isNotEmpty;
    final endash = String.fromCharCode(0x2014);
    return RichText(
      text: TextSpan(
        style: const TextStyle(fontSize: 12.5, color: AppColors.textBody, height: 1.3),
        children: [
          TextSpan(text: label, style: const TextStyle(fontWeight: FontWeight.w600)),
          TextSpan(text: ' $endash '),
          TextSpan(
            text: hasValue ? value : placeholder,
            style: TextStyle(
              color: hasValue ? AppColors.textBody : AppColors.textFaint,
              fontStyle: hasValue ? FontStyle.normal : FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  Widget _manualModelField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _manualModel,
          onChanged: (value) {
            setState(() {
              final trimmed = value.trim();
              _model = trimmed.isEmpty ? null : trimmed;
            });
          },
          decoration: InputDecoration(
            hintText: 'Type model number...',
            hintStyle: const TextStyle(color: AppColors.textFaint),
            filled: true,
            fillColor: AppColors.card,
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: AppColors.divider),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: AppColors.divider),
            ),
          ),
        ),
        TextButton(
          onPressed: _scanning ? null : _choosePlatePhoto,
          child: const Text('Choose from photos'),
        ),
      ],
    );
  }

  Widget _startingState() {
    return const Padding(
      padding: EdgeInsets.only(bottom: 12),
      child: Text('Starting a new issue...', style: TextStyle(color: AppColors.textFaint, fontSize: 12)),
    );
  }

  Widget _startError() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Could not start a new issue.', style: TextStyle(color: AppColors.textBody2, fontSize: 12)),
          const SizedBox(height: 8),
          TextButton(onPressed: _init, child: const Text('Retry')),
        ],
      ),
    );
  }

  Widget _inlineError() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Text(
        _error!,
        style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
      ),
    );
  }

  Widget _startButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        onPressed: _startDiagnosis,
        child: const Text('Start diagnosis', style: TextStyle(fontWeight: FontWeight.w700)),
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
                  hintText: 'Describe your appliance problem...',
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
                onPressed: _scanPlate,
                icon: const Icon(Icons.photo_camera_outlined, color: AppColors.textBody2),
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
