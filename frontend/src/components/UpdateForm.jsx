import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { MILESTONES } from './Timeline';

const AUDIENCE_OPTIONS = [
  { value: 'public', label: 'Public', hint: 'Anyone with the link can see' },
  { value: 'group_targeted', label: 'Family', hint: 'Only invited family viewers' },
  { value: 'parents_only', label: 'Parents only', hint: 'Just you and your co-parent' },
];

export default function UpdateForm({ birthId, onSuccess }) {
  const [mode, setMode] = useState(null); // 'photo' | 'note' | 'milestone' | 'audio'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [audienceScope, setAudienceScope] = useState('public');

  const [noteText, setNoteText] = useState('');
  const [selectedMilestone, setSelectedMilestone] = useState('');
  const [milestoneNote, setMilestoneNote] = useState('');
  const [photoCaption, setPhotoCaption] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);

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

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const resetForm = () => {
    setMode(null);
    setError('');
    setNoteText('');
    setSelectedMilestone('');
    setMilestoneNote('');
    setPhotoCaption('');
    setSelectedFile(null);
    setPreview(null);
    setAudienceScope('public');
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl(null);
    setAudioCaption('');
    setAudioMimeType('audio/webm');
    setRecordingTime(0);
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target.result);
    reader.readAsDataURL(file);
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
      await api.createTextNote(birthId, noteText, { audienceScope });
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
      });
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message);
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

  if (!mode) {
    return (
      <div className="card">
        <div className="flex flex-wrap gap-3 justify-center">
          <ModeButton mode="photo" color="primary" onClick={() => setMode('photo')}>
            Photo
          </ModeButton>
          <ModeButton mode="note" color="blue" onClick={() => setMode('note')}>
            Note
          </ModeButton>
          <ModeButton mode="milestone" color="amber" onClick={() => setMode('milestone')}>
            Milestone
          </ModeButton>
          <ModeButton mode="audio" color="rose" onClick={() => setMode('audio')}>
            Voice Memo
          </ModeButton>
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
            {Object.entries(MILESTONES).map(([key, { label, icon }]) => (
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
              : mode === 'note' ? submitNote
                : mode === 'audio' ? submitAudio
                  : submitMilestone
          }
          disabled={
            loading
            || (mode === 'photo' && !selectedFile)
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

function ModeButton({ children, color, onClick }) {
  const palette = {
    primary: 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 hover:bg-primary-100 dark:hover:bg-primary-900/50',
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50',
    amber: 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50',
    rose: 'bg-rose-50 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/50',
  };
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 rounded-xl font-medium transition-colors ${palette[color]}`}
    >
      {children}
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
