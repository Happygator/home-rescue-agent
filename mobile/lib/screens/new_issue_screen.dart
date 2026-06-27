import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../services/media_capture.dart';
import '../services/upload.dart';
import '../theme.dart';
import '../widgets/app_header.dart';
import 'issue_detail_screen.dart';

/// Intake composer: the user describes the problem (and optionally attaches a photo) BEFORE the
/// chat opens. On submit we create the case, seed that description as the first user message in the
/// transcript, and hand off to the chat screen, where the agent auto-starts with this context.
class NewIssueScreen extends StatefulWidget {
  final String? appliance;
  final ApiClient? client;

  // Injectable capture: returns photo bytes, or null if the user/camera denied/cancelled.
  // Default uses the device camera; tests can override it.
  final Future<List<int>?> Function()? capturePhoto;

  const NewIssueScreen({
    super.key,
    this.appliance,
    this.client,
    this.capturePhoto,
  });

  @override
  State<NewIssueScreen> createState() => _NewIssueScreenState();
}

class _NewIssueScreenState extends State<NewIssueScreen> {
  late final ApiClient _api = widget.client ?? ApiClient();
  final _text = TextEditingController();
  List<int>? _photo;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _text.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<List<int>?> _defaultCapture() => MediaCapture().capturePhoto();

  Future<void> _attachPhoto() async {
    if (_submitting) return;
    final bytes = await (widget.capturePhoto ?? _defaultCapture)();
    if (!mounted || bytes == null) return;
    setState(() => _photo = bytes);
  }

  Future<void> _attachFromLibrary() async {
    if (_submitting) return;
    final bytes = await MediaCapture().pickFromGallery();
    if (!mounted || bytes == null) return;
    setState(() => _photo = bytes);
  }

  Future<void> _start() async {
    final text = _text.text.trim();
    if (text.isEmpty || _submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final caseId = await _api.createIssue(
        appliance: widget.appliance,
        symptom: text,
      );
      String? ref;
      if (_photo != null) {
        ref = await uploadMediaWithRetry(
          _api,
          caseId,
          _photo!,
          filename: 'symptom.jpg',
          kind: 'symptom',
        );
      }
      // Seed the description as the first user message so it shows in chat history and the agent's
      // auto-kickoff has it to work from. The image (if any) rides along via media_ref.
      await _api.updateIssue(
        caseId,
        messages: [
          {'role': 'user', 'text': text, if (ref != null) 'media_ref': ref},
        ],
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) =>
              IssueDetailScreen(caseId: caseId, client: widget.client),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = 'Could not start your issue. Please try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final canStart = _text.text.trim().isNotEmpty && !_submitting;
    return Scaffold(
      backgroundColor: AppColors.bg,
      resizeToAvoidBottomInset: true,
      body: Column(
        children: [
          const AppHeader(title: 'New Issue', showBack: true),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                  "What's going on with your appliance?",
                  style: TextStyle(
                    color: AppColors.textTitle,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Describe what it’s doing wrong. Add a photo of the problem or the spec plate if you can — it helps the assistant diagnose faster.',
                  style: TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 13,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 16),
                _descriptionField(),
                const SizedBox(height: 14),
                _photoArea(),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: const TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 12,
                    ),
                  ),
                ],
              ],
            ),
          ),
          _bottomBar(canStart),
        ],
      ),
    );
  }

  String get _descriptionHint {
    switch (widget.appliance?.toLowerCase()) {
      case 'dishwasher':
        return 'e.g. The dishwasher runs but dishes come out dirty...';
      case 'washer':
        return 'e.g. The washer fills but won\'t spin or drain...';
      case 'refrigerator':
      case 'fridge':
        return 'e.g. The fridge is running but the fresh-food side is warm...';
      default:
        return 'e.g. Describe what the appliance is doing wrong...';
    }
  }

  Widget _descriptionField() {
    return TextField(
      controller: _text,
      minLines: 4,
      maxLines: 8,
      textInputAction: TextInputAction.newline,
      decoration: InputDecoration(
        hintText: _descriptionHint,
        hintStyle: const TextStyle(color: AppColors.textFaint),
        filled: true,
        fillColor: AppColors.card,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 12,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.divider),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.primary),
        ),
      ),
    );
  }

  Widget _photoArea() {
    if (_photo != null) {
      return Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.memory(
              Uint8List.fromList(_photo!),
              width: 64,
              height: 64,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => Container(
                width: 64,
                height: 64,
                color: AppColors.card,
                child: const Icon(
                  Icons.image_outlined,
                  color: AppColors.textFaint,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Text(
              'Photo attached',
              style: TextStyle(color: AppColors.textBody2, fontSize: 13),
            ),
          ),
          TextButton(
            onPressed: _submitting ? null : () => setState(() => _photo = null),
            child: const Text('Remove'),
          ),
        ],
      );
    }
    return Wrap(
      spacing: 8,
      runSpacing: 4,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        OutlinedButton.icon(
          onPressed: _submitting ? null : _attachPhoto,
          icon: const Icon(Icons.photo_camera_outlined, size: 18),
          label: const Text('Add a photo'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.textBody2,
            side: const BorderSide(color: AppColors.divider),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          ),
        ),
        TextButton(
          onPressed: _submitting ? null : _attachFromLibrary,
          child: const Text('Choose from photos'),
        ),
      ],
    );
  }

  Widget _bottomBar(bool canStart) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.bg,
          border: Border(top: BorderSide(color: AppColors.divider)),
        ),
        padding: const EdgeInsets.all(12),
        child: SizedBox(
          width: double.infinity,
          height: 48,
          child: FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              disabledBackgroundColor: AppColors.divider,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            onPressed: canStart ? _start : null,
            child: _submitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Text(
                    'Start diagnosis',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
          ),
        ),
      ),
    );
  }
}
