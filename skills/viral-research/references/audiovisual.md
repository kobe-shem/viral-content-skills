# Audiovisual study

Prepare an existing authorized local video with the bundled helper (Python 3.9+, `ffmpeg` and `ffprobe` on PATH). Replace `/path/to/viral-research` with the installed skill directory:

```bash
python3 /path/to/viral-research/scripts/media.py probe project/private/source.mp4
python3 /path/to/viral-research/scripts/media.py prepare project/private/source.mp4 --out project/private/evidence/creative-v1
```

This produces a source hash, metadata, dense first-five-second frames, regular samples across the duration, and an audio file when present. Its output is **prepared evidence**, not analysis. Existing output is never overwritten. For long videos deliberately choose an interval/frame budget or document the excerpt; do not silently inspect the first few minutes and call the whole video reviewed. Media and private paths remain outside the skill repository.

## Complete the observations

1. Preserve the raw source URL/ID, capture date and file hash in the corpus. Note whether the file is a full creative, compilation, repost, edited excerpt or teacher commentary containing another ad.
2. Obtain the complete timecoded transcript. Prefer the media's actual audio, supplied captions, or a verified provider transcript. Check names, figures and crucial words against audio. Retain uncertainty and transcription errors instead of inventing a clean quotation.
3. Inspect the dense opening frames. Transcribe text that is actually visible. Record composition, first physical action, camera, props, relevant gesture and any gap between the picture's promise and spoken line. A post caption is a separate field.
4. Follow the entire argument with timecodes. Around each reveal, role switch, visual claim and suspected cut, inspect additional frames or continuous playback. A sample interval is not a measured shot duration. Differentiate sampled observation from frame-accurate timing.
5. Review the sound separately with playback or a capable audio/video analysis tool: emphasis, breath, pauses, background music, scene sounds, sound effects and their relationship to the picture. Mark model-derived observations as such. A transcript alone cannot support an audio-style conclusion.
6. If using a video analysis service, reconcile its scene descriptions with the source frames/transcript. Generic provider labels often mistake a closing claim for a CTA or every segment for a new shot. A semantic segment is not a camera cut. Reject unsupported technical, demographic or performance assertions.
7. Record the closing payoff, CTA if any, final frame/hold, and whether the opening was fulfilled. Document deliberate restraint, not only effects.

## Observation card

For each meaningful beat record time range, exact spoken words or paraphrase status, exact screen text or uncertainty, pictured action, framing/movement, delivery/audio, transition, active viewer question, new reward, source/proof status, and confidence. Separately record what was **taught**, what was **observed**, and your interpretation of its purpose.

Study matched high, typical and low examples before deciding a habit explains performance. The same framing or subtitle treatment appearing in all three is often a house style. A low-view post can still be valuable for conversion, authority or an audience subset.

## Transfer to editing

Describe reproducible decisions: a hard cut reveals the second character's reaction; the title holds while captions move; a physical prop changes state before the speaker explains it; sound announces an off-screen event. Specify the reason and exception, not “cut every 1.2 seconds.”

Use `video-style-study` for a measured style pack when installed. Hand exact words and narrative cues to `viral-direct`; actual recording and measured media are needed before `video-edit` builds its final timeline. Do not infer lip sync, full pacing or safe text placement from an incomplete source.
