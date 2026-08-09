import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { MILESTONES } from './Timeline';
import { toLocalInputValue } from '../utils/relativeTime';

// Two tiers, not three. "Public" used to sit on top, promising "anyone with
// the link can see" — which was never true, and shouldn't be: the page is
// private, and everyone reading it got in with an invite. It was also the
// default, so it collected every post anyone ever made without being chosen.
const AUDIENCE_OPTIONS = [
  { value: 'group_targeted', label: 'Family', hint: 'Everyone you invited' },
  { value: 'parents_only', label: 'Parents only', hint: 'Just you and your co-parent' },
];

// `onBabyBorn(occurredAtISO)` announces the birth; pass null once it's been
// announced and the button drops out of the row. `joinedBelow` squares off the
// bottom edge so the composer and the timeline read as one surface — the
// composer isn't a tool that happens to sit near the story, it's the top of it.
export default function UpdateForm({
  birthId,
  onSuccess,
  onBabyBorn = null,
  childName = null,
  authorName = '',
  joinedBelow = false,
  // Lets the arrival nudge drive the composer straight into born mode, so
  // "Mark it" lands on the real form with its real question rather than
  // flipping the birth behind the parent's back on a guessed timestamp.
  openBornMode = false,
  onBornModeOpened = null,
}) {
  const [mode, setMode] = useState(null); // 'photo' | 'note' | 'milestone' | 'audio' | 'video' | 'born'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [bornTime, setBornTime] = useState('');
  const [audienceScope, setAudienceScope] = useState('group_targeted');
  // '' = happening now (server stamps the time); otherwise a local
  // datetime the parent picked because they're logging after the fact
  const [backdate, setBackdate] = useState('');

  const [noteText, setNoteText] = useState('');
  const [selectedMilestone, setSelectedMilestone] = useState('');
  const [milestoneNote, setMilestoneNote] = useState('');
  const [photoCaption, setPhotoCaption] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [selectedVideoFile, setSelectedVideoFile] = useState(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(null);
  const [videoCaption, setVideoCaption] = useState('');

  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioCaption, setAudioCaption] = useState('');
  const [audioMimeType, setAudioMimeType] = useState('audio/webm');
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  const fileInputRef = useRef(null);
  const videoFileInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  useEffect(() => {
    return () => {
      if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    };
  }, [videoPreviewUrl]);

  const resetForm = () => {
    setMode(null);
    setError('');
    setBornTime('');
    setBackdate('');
    setNoteText('');
    setSelectedMilestone('');
    setMilestoneNote('');
    setPhotoCaption('');
    setSelectedFile(null);
    setPreview(null);
    if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    setSelectedVideoFile(null);
    setVideoPreviewUrl(null);
    setVideoCaption('');
    setAudienceScope('group_targeted');
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl(null);
    setAudioCaption('');
    setAudioMimeType('audio/webm');
    setRecordingTime(0);
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const occurredAt = () => (backdate ? new Date(backdate).toISOString() : null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const clearVideoSelection = () => {
    if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    setSelectedVideoFile(null);
    setVideoPreviewUrl(null);
    if (videoFileInputRef.current) videoFileInputRef.current.value = '';
  };

  const handleVideoSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    setSelectedVideoFile(file);
    setVideoPreviewUrl(URL.createObjectURL(file));
  };

  const submitPhoto = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setError('');
    try {
      await api.uploadMedia(birthId, {
        file: selectedFile,
        kind: 'photo',
        caption: photoCaption,
        audienceScope,
        occurredAt: occurredAt(),
      });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitNote = async () => {
    if (!noteText.trim()) return;
    setLoading(true);
    setError('');
    try {
      await api.createTextNote(birthId, noteText, { audienceScope, occurredAt: occurredAt() });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitMilestone = async () => {
    if (!selectedMilestone) return;
    setLoading(true);
    setError('');
    try {
      await api.createMilestone(birthId, {
        kind: selectedMilestone,
        title: MILESTONES[selectedMilestone]?.label,
        body: milestoneNote || null,
        audienceScope,
        occurredAt: occurredAt(),
      });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitBorn = async () => {
    setLoading(true);
    setError('');
    try {
      await onBabyBorn(bornTime ? new Date(bornTime).toISOString() : null);
      resetForm();
    } catch (err) {
      // Stay on the form and say why. Closing regardless would look exactly
      // like a successful announcement, which is the worst possible outcome
      // here — the parent would think the family had been told.
      setError(err.message || 'Could not announce the birth');
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';
      else if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mimeType = 'audio/webm;codecs=opus';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      setAudioMimeType(mimeType);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => setRecordingTime((t) => t + 1), 1000);
    } catch {
      setError('Could not access microphone. Please allow microphone access.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const discardRecording = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingTime(0);
  };

  const submitAudio = async () => {
    if (!audioBlob) return;
    setLoading(true);
    setError('');
    try {
      const ext = audioMimeType.includes('mp4') ? '.m4a' : '.webm';
      const file = new File([audioBlob], `voice-memo${ext}`, { type: audioMimeType });
      await api.uploadMedia(birthId, {
        file,
        kind: 'voice_memo',
        caption: audioCaption,
        audienceScope,
        occurredAt: occurredAt(),
      });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitVideo = async () => {
    if (!selectedVideoFile) return;
    setLoading(true);
    setError('');
    try {
      await api.uploadMedia(birthId, {
        file: selectedVideoFile,
        kind: 'video',
        caption: videoCaption,
        audienceScope,
        occurredAt: occurredAt(),
      });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatRecordingTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (!openBornMode || !onBabyBorn) return;
    setBornTime(toLocalInputValue());
    setMode('born');
    onBornModeOpened?.();
  }, [openBornMode, onBabyBorn, onBornModeOpened]);

  const initial = (authorName || '').trim().charAt(0).toUpperCase() || '🤍';
  const placeholder = childName
    ? `Share something with ${childName}'s family…`
    : 'Share something with the family…';

  // The resting state: one open field, not a rack of type buttons. You start
  // with a thought — "she's doing so well" — and reach for a medium only if
  // you have one. Six equal-weight buttons made you name the file type before
  // you'd had the thought, and put a decision in front of every single post.
  //
  // Attachments stay quiet and secondary. Photo and Voice lead because they're
  // what actually gets used between contractions; Video and Milestone follow.
  if (!mode) {
    return (
      <div className={`card ${joinedBelow ? 'rounded-b-none border-b-0 pb-4' : ''}`}>
        <div className="flex gap-3 items-center">
          <div
            className="w-10 h-10 rounded-full grid place-items-center font-semibold text-sm shrink-0"
            style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-accent)' }}
          >
            {initial}
          </div>
          <button
            type="button"
            onClick={() => setMode('note')}
            className="flex-1 text-left px-5 py-3 rounded-full border text-[0.98rem] transition-colors"
            style={{
              borderColor: 'var(--t-soft-ring)',
              color: 'var(--t-ink-faint)',
              backgroundColor: 'var(--t-note-bg)',
            }}
          >
            {placeholder}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-1 mt-3 sm:pl-[52px]">
          <AttachButton icon="📷" label="Photo" onClick={() => setMode('photo')} />
          <AttachButton icon="🎙️" label="Voice" onClick={() => setMode('audio')} />
          <AttachButton icon="🎥" label="Video" onClick={() => setMode('video')} />
          <AttachButton icon="⭐" label="Milestone" onClick={() => setMode('milestone')} />
          {/* Announcing is one of these — you're posting to the timeline, and
              it IS a milestone (kind: 'born'). It's marked rather than
              shouted, and pushed to the far end: an announcement that can't be
              un-tapped without undoing the whole flip shouldn't sit under the
              thumb that's reaching for Photo. */}
          {onBabyBorn && (
            <button
              type="button"
              onClick={() => {
                setBornTime(toLocalInputValue());
                setMode('born');
              }}
              className="sm:ml-auto flex items-center gap-2 px-3 py-2 rounded-lg
                         text-sm font-bold border transition-colors"
              style={{
                backgroundColor: 'var(--t-soft-bg)',
                color: 'var(--t-accent)',
                borderColor: 'var(--t-accent)',
              }}
            >
              👶 Mark baby born
            </button>
          )}
        </div>
      </div>
    );
  }

  // The announcement doesn't take an audience or a backdate — it's always the
  // widest tier, and its time is the arrival itself — so it skips the shared
  // composer body and footer entirely.
  if (mode === 'born') {
    return (
      <div className="card flex flex-col items-center gap-3 py-5">
        {error && (
          <div className="w-full mb-1 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg text-sm">
            {error}
          </div>
        )}
        {/* Lead with the time, not the confirmation. Nobody taps this while
            it's happening — you post once you have a free hand, so the
            prefilled "now" is nearly always late by 15-40 minutes. Asking the
            question outright gets the real time on the record; burying it
            under a confirm button got it corrected afterwards, if at all. */}
        <label className="flex flex-col items-center gap-2">
          <span className="text-base font-medium t-ink text-center">
            When did they arrive?
          </span>
          <input
            type="datetime-local"
            value={bornTime}
            onChange={(e) => setBornTime(e.target.value)}
            max={toLocalInputValue()}
            className="px-3 py-2 rounded-lg border text-base bg-white dark:bg-gray-800 t-ink"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          />
        </label>
        <p className="text-xs t-muted text-center">
          Set to now — nudge it back if the moment has already passed.
        </p>
        <div className="flex gap-2">
          <button
            onClick={submitBorn}
            disabled={loading}
            className="px-5 py-2.5 rounded-full t-btn-accent font-medium disabled:opacity-50"
          >
            {loading ? 'Announcing…' : '🎉 Baby Born!'}
          </button>
          <button
            onClick={resetForm}
            disabled={loading}
            className="px-4 py-2.5 rounded-full text-sm t-muted hover:opacity-80"
          >
            Not yet
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      {error && (
        <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg text-sm">
          {error}
        </div>
      )}

      {mode === 'photo' && (
        <div className="space-y-4">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept="image/*"
            className="hidden"
          />
          {preview ? (
            <div className="relative">
              <img src={preview} alt="Preview" className="w-full rounded-xl max-h-64 object-cover" />
              <button
                onClick={() => { setSelectedFile(null); setPreview(null); }}
                className="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white"
              >
                <CloseIcon />
              </button>
            </div>
          ) : (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-12 border-2 border-dashed border-gray-300 dark:border-gray-600
                         rounded-xl text-gray-500 dark:text-gray-400 hover:border-primary-400
                         hover:text-primary-500 transition-colors"
            >
              Tap to select photo
            </button>
          )}
          <input
            type="text"
            value={photoCaption}
            onChange={(e) => setPhotoCaption(e.target.value)}
            placeholder="Add a caption (optional)"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          />
        </div>
      )}

      {mode === 'video' && (
        <div className="space-y-4">
          <input
            type="file"
            ref={videoFileInputRef}
            onChange={handleVideoSelect}
            accept="video/*"
            className="hidden"
          />
          {videoPreviewUrl ? (
            <div className="relative">
              <video
                src={videoPreviewUrl}
                controls
                className="w-full rounded-xl max-h-64 bg-black"
              />
              <button
                type="button"
                onClick={clearVideoSelection}
                className="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white"
              >
                <CloseIcon />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => videoFileInputRef.current?.click()}
              className="w-full py-12 border-2 border-dashed border-gray-300 dark:border-gray-600
                         rounded-xl text-gray-500 dark:text-gray-400 hover:border-violet-400
                         hover:text-violet-500 transition-colors"
            >
              Tap to select video
            </button>
          )}
          <input
            type="text"
            value={videoCaption}
            onChange={(e) => setVideoCaption(e.target.value)}
            placeholder="Add a caption (optional)"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          />
        </div>
      )}

      {mode === 'note' && (
        <textarea
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          placeholder="What's happening?"
          rows={3}
          className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 resize-none"
        />
      )}

      {mode === 'milestone' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(MILESTONES)
              .filter(([key]) => key !== 'born')
              .map(([key, { label, icon }]) => (
              <button
                key={key}
                onClick={() => setSelectedMilestone(key)}
                className={`p-3 rounded-xl text-left transition-colors ${
                  selectedMilestone === key
                    ? 'bg-primary-100 dark:bg-primary-900/50 border-2 border-primary-500'
                    : 'bg-gray-50 dark:bg-gray-700/50 border-2 border-transparent'
                }`}
              >
                <span className="text-xl mr-2">{icon}</span>
                <span className="text-sm">{label}</span>
              </button>
            ))}
          </div>
          <input
            type="text"
            value={milestoneNote}
            onChange={(e) => setMilestoneNote(e.target.value)}
            placeholder="Add details (optional)"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          />
        </div>
      )}

      {mode === 'audio' && (
        <div className="space-y-4">
          {!audioBlob ? (
            <div className="flex flex-col items-center py-8">
              {isRecording ? (
                <>
                  <div className="w-20 h-20 rounded-full bg-red-500 flex items-center justify-center animate-pulse mb-4">
                    <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                  </div>
                  <p className="text-2xl font-mono text-red-500 mb-4">
                    {formatRecordingTime(recordingTime)}
                  </p>
                  <button
                    onClick={stopRecording}
                    className="px-6 py-3 bg-red-500 text-white rounded-xl font-medium hover:bg-red-600"
                  >
                    Stop Recording
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={startRecording}
                    className="w-20 h-20 rounded-full bg-rose-500 hover:bg-rose-600 flex items-center justify-center transition-colors mb-4"
                  >
                    <MicIcon />
                  </button>
                  <p className="text-gray-500 dark:text-gray-400">Tap to record</p>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-rose-500"><MicIcon small /></span>
                  <span className="text-gray-600 dark:text-gray-300">
                    Voice memo ({formatRecordingTime(recordingTime)})
                  </span>
                  <button
                    onClick={discardRecording}
                    className="ml-auto p-1 text-gray-400 hover:text-red-500"
                  >
                    <CloseIcon />
                  </button>
                </div>
                <audio src={audioUrl} controls className="w-full" />
              </div>
              <input
                type="text"
                value={audioCaption}
                onChange={(e) => setAudioCaption(e.target.value)}
                placeholder="Add a caption (optional)"
                className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                           bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              />
            </div>
          )}
        </div>
      )}

      <AudiencePicker value={audienceScope} onChange={setAudienceScope} />

      <div className="mt-3">
        {backdate ? (
          <div className="flex items-center gap-2">
            <input
              type="datetime-local"
              value={backdate}
              onChange={(e) => setBackdate(e.target.value)}
              max={toLocalInputValue()}
              className="flex-1 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700
                         bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm"
            />
            <button
              type="button"
              onClick={() => setBackdate('')}
              className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              Just now
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setBackdate(toLocalInputValue())}
            className="text-xs text-gray-400 hover:text-primary-500"
          >
            {/* The question is context; only "Set the time" does anything, so
                it's the part that carries the underline. */}
            Happened earlier? <span className="underline">Set the time</span>
          </button>
        )}
      </div>

      <div className="flex gap-3 mt-4">
        <button
          onClick={resetForm}
          className="flex-1 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                     text-gray-600 dark:text-gray-400 font-medium"
        >
          Cancel
        </button>
        <button
          onClick={
            mode === 'photo' ? submitPhoto
              : mode === 'video' ? submitVideo
                : mode === 'note' ? submitNote
                  : mode === 'audio' ? submitAudio
                    : submitMilestone
          }
          disabled={
            loading
            || (mode === 'photo' && !selectedFile)
            || (mode === 'video' && !selectedVideoFile)
            || (mode === 'note' && !noteText.trim())
            || (mode === 'milestone' && !selectedMilestone)
            || (mode === 'audio' && !audioBlob)
          }
          className="flex-1 py-3 rounded-xl bg-primary-600 text-white font-medium
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Posting…' : 'Post'}
        </button>
      </div>
    </div>
  );
}

function AudiencePicker({ value, onChange }) {
  const active = AUDIENCE_OPTIONS.find((o) => o.value === value) || AUDIENCE_OPTIONS[0];
  return (
    <div className="mt-4">
      <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
        {AUDIENCE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex-1 px-3 py-2 text-xs font-medium rounded-md transition-colors ${
              value === opt.value
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
        {active.hint}
      </p>
    </div>
  );
}

// Secondary by design: no fill at rest, so the row reads as a set of options
// available to the field above rather than five competing buttons. The colour
// only arrives on hover, once you've aimed at one.
function AttachButton({ icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold
                 t-muted hover:t-ink transition-colors"
      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--t-soft-bg)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
    >
      <span className="text-base leading-none">{icon}</span>
      {label}
    </button>
  );
}

function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function MicIcon({ small = false }) {
  const cls = small ? 'w-5 h-5' : 'w-10 h-10 text-white';
  return (
    <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  );
}
