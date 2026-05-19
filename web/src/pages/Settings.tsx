import React, { useState } from 'react';
import { I } from '../components/Icons';
import { Topbar } from '../components/Topbar';
import { CHANNEL, CHARACTERS } from '../data/mock';
import type { Character } from '../types';

/* --- SliderRow --- */

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange?: (v: number) => void;
  suffix?: string;
}

const SliderRow: React.FC<SliderRowProps> = ({ label, value, min, max, step, onChange, suffix }) => (
  <div className="slider-row">
    <label className="slider-row__label">{label}</label>
    <input
      type="range"
      className="slider-row__input"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange?.(parseFloat(e.target.value))}
    />
    <span className="slider-row__value">
      {value}{suffix ?? ''}
    </span>
  </div>
);

/* --- Settings page local state --- */

interface ChannelSettings {
  name: string;
  file: string;
  game_language: string;
  default_language: string;
}

interface AsrSettings {
  model_size: string;
  device: string;
  vad_threshold: number;
  beam_size: number;
}

interface ChatSettings {
  spike_threshold: number;
  window: number;
  max_messages: number;
  sc_min_amount: number;
}

interface OcrSettings {
  sample_interval: number;
  hash_threshold: number;
  min_duration: number;
  max_duration: number;
}

interface ScoringWeights {
  volume: number;
  laughter: number;
  keyword: number;
  chat: number;
  speech_rate: number;
  silence_burst: number;
  threshold: number;
}

interface CharEntry {
  id: string;
  name: string;
  aliases: string;
  color: string;
  lines: number;
}

export const SettingsPage: React.FC = () => {
  // Channel
  const [channel, setChannel] = useState<ChannelSettings>({
    name: CHANNEL.name,
    file: CHANNEL.file,
    game_language: CHANNEL.game_language,
    default_language: CHANNEL.default_language,
  });

  // ASR
  const [asr, setAsr] = useState<AsrSettings>({
    model_size: 'large-v3',
    device: 'cuda',
    vad_threshold: 0.5,
    beam_size: 5,
  });

  // Chat
  const [chat, setChat] = useState<ChatSettings>({
    spike_threshold: 2.5,
    window: 30,
    max_messages: 200,
    sc_min_amount: 100,
  });

  // OCR
  const [ocr, setOcr] = useState<OcrSettings>({
    sample_interval: 0.5,
    hash_threshold: 8,
    min_duration: 1.0,
    max_duration: 30.0,
  });

  // Scoring
  const [scoring, setScoring] = useState<ScoringWeights>({
    volume: 15,
    laughter: 20,
    keyword: 20,
    chat: 25,
    speech_rate: 10,
    silence_burst: 10,
    threshold: 60,
  });

  // Characters
  const [chars, setChars] = useState<CharEntry[]>(
    CHARACTERS.map((c) => ({
      id: c.id,
      name: c.name,
      aliases: c.aliases.join(', '),
      color: c.color,
      lines: c.lines,
    }))
  );

  const updateChar = (id: string, field: keyof CharEntry, value: string) => {
    setChars((prev) => prev.map((c) => c.id === id ? { ...c, [field]: value } : c));
  };

  const deleteChar = (id: string) => {
    setChars((prev) => prev.filter((c) => c.id !== id));
  };

  const addChar = () => {
    const newId = `char_${Date.now()}`;
    setChars((prev) => [...prev, { id: newId, name: '', aliases: '', color: '#888888', lines: 0 }]);
  };

  const topbarActions = (
    <>
      <button className="btn btn--sm"><I.Upload size={14} /> Load YAML</button>
      <button className="btn btn--sm"><I.Download size={14} /> Export YAML</button>
    </>
  );

  return (
    <div className="page page--settings">
      <Topbar title="Settings" jpTitle="設定" actions={topbarActions} />

      <div className="settings-body">
        {/* Channel Info */}
        <section className="settings-section">
          <h3 className="settings-section__title">頻道資訊</h3>
          <div className="settings-grid">
            <div className="settings-field">
              <label>Name</label>
              <input
                type="text"
                value={channel.name}
                onChange={(e) => setChannel({ ...channel, name: e.target.value })}
              />
            </div>
            <div className="settings-field">
              <label>File</label>
              <input
                type="text"
                value={channel.file}
                onChange={(e) => setChannel({ ...channel, file: e.target.value })}
              />
            </div>
            <div className="settings-field">
              <label>Game Language</label>
              <input
                type="text"
                value={channel.game_language}
                onChange={(e) => setChannel({ ...channel, game_language: e.target.value })}
              />
            </div>
            <div className="settings-field">
              <label>Default Language</label>
              <input
                type="text"
                value={channel.default_language}
                onChange={(e) => setChannel({ ...channel, default_language: e.target.value })}
              />
            </div>
          </div>
        </section>

        {/* ASR */}
        <section className="settings-section">
          <h3 className="settings-section__title">ASR</h3>
          <div className="settings-grid">
            <div className="settings-field">
              <label>Model Size</label>
              <select
                value={asr.model_size}
                onChange={(e) => setAsr({ ...asr, model_size: e.target.value })}
              >
                <option value="tiny">tiny</option>
                <option value="base">base</option>
                <option value="small">small</option>
                <option value="medium">medium</option>
                <option value="large-v2">large-v2</option>
                <option value="large-v3">large-v3</option>
              </select>
            </div>
            <div className="settings-field">
              <label>Device</label>
              <select
                value={asr.device}
                onChange={(e) => setAsr({ ...asr, device: e.target.value })}
              >
                <option value="cuda">cuda</option>
                <option value="cpu">cpu</option>
              </select>
            </div>
          </div>
          <SliderRow
            label="VAD Threshold"
            value={asr.vad_threshold}
            min={0.1}
            max={1.0}
            step={0.05}
            onChange={(v) => setAsr({ ...asr, vad_threshold: v })}
          />
          <SliderRow
            label="Beam Size"
            value={asr.beam_size}
            min={1}
            max={10}
            step={1}
            onChange={(v) => setAsr({ ...asr, beam_size: v })}
          />
        </section>

        {/* CHAT */}
        <section className="settings-section">
          <h3 className="settings-section__title">CHAT</h3>
          <SliderRow
            label="Spike Threshold"
            value={chat.spike_threshold}
            min={1.0}
            max={5.0}
            step={0.1}
            suffix="x"
            onChange={(v) => setChat({ ...chat, spike_threshold: v })}
          />
          <SliderRow
            label="Window"
            value={chat.window}
            min={10}
            max={120}
            step={5}
            suffix="s"
            onChange={(v) => setChat({ ...chat, window: v })}
          />
          <SliderRow
            label="Max Messages"
            value={chat.max_messages}
            min={50}
            max={500}
            step={10}
            onChange={(v) => setChat({ ...chat, max_messages: v })}
          />
          <SliderRow
            label="SC Min Amount"
            value={chat.sc_min_amount}
            min={0}
            max={1000}
            step={50}
            suffix=" JPY"
            onChange={(v) => setChat({ ...chat, sc_min_amount: v })}
          />
        </section>

        {/* OCR */}
        <section className="settings-section">
          <h3 className="settings-section__title">OCR</h3>
          <SliderRow
            label="Sample Interval"
            value={ocr.sample_interval}
            min={0.1}
            max={2.0}
            step={0.1}
            suffix="s"
            onChange={(v) => setOcr({ ...ocr, sample_interval: v })}
          />
          <SliderRow
            label="Hash Threshold"
            value={ocr.hash_threshold}
            min={1}
            max={20}
            step={1}
            onChange={(v) => setOcr({ ...ocr, hash_threshold: v })}
          />
          <SliderRow
            label="Min Duration"
            value={ocr.min_duration}
            min={0.5}
            max={5.0}
            step={0.5}
            suffix="s"
            onChange={(v) => setOcr({ ...ocr, min_duration: v })}
          />
          <SliderRow
            label="Max Duration"
            value={ocr.max_duration}
            min={10}
            max={60}
            step={5}
            suffix="s"
            onChange={(v) => setOcr({ ...ocr, max_duration: v })}
          />
        </section>

        {/* SCORING */}
        <section className="settings-section">
          <h3 className="settings-section__title">SCORING</h3>
          <SliderRow
            label="Volume"
            value={scoring.volume}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, volume: v })}
          />
          <SliderRow
            label="Laughter"
            value={scoring.laughter}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, laughter: v })}
          />
          <SliderRow
            label="Keyword"
            value={scoring.keyword}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, keyword: v })}
          />
          <SliderRow
            label="Chat"
            value={scoring.chat}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, chat: v })}
          />
          <SliderRow
            label="Speech Rate"
            value={scoring.speech_rate}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, speech_rate: v })}
          />
          <SliderRow
            label="Silence Burst"
            value={scoring.silence_burst}
            min={0}
            max={50}
            step={1}
            onChange={(v) => setScoring({ ...scoring, silence_burst: v })}
          />
          <SliderRow
            label="Score Threshold"
            value={scoring.threshold}
            min={10}
            max={100}
            step={5}
            onChange={(v) => setScoring({ ...scoring, threshold: v })}
          />
          <div className="settings-weight-total">
            Total Weight: {scoring.volume + scoring.laughter + scoring.keyword + scoring.chat + scoring.speech_rate + scoring.silence_burst}
            {(scoring.volume + scoring.laughter + scoring.keyword + scoring.chat + scoring.speech_rate + scoring.silence_burst) !== 100 && (
              <span className="settings-weight-warn"> (should be 100)</span>
            )}
          </div>
        </section>

        {/* Characters */}
        <section className="settings-section">
          <h3 className="settings-section__title">角色管理</h3>
          <div className="settings-char-list">
            {chars.map((ch) => (
              <div key={ch.id} className="settings-char-row">
                <input
                  type="color"
                  className="settings-char-row__color"
                  value={ch.color}
                  onChange={(e) => updateChar(ch.id, 'color', e.target.value)}
                />
                <input
                  type="text"
                  className="settings-char-row__name"
                  placeholder="Name"
                  value={ch.name}
                  onChange={(e) => updateChar(ch.id, 'name', e.target.value)}
                />
                <input
                  type="text"
                  className="settings-char-row__aliases"
                  placeholder="Aliases (comma separated)"
                  value={ch.aliases}
                  onChange={(e) => updateChar(ch.id, 'aliases', e.target.value)}
                />
                <span className="settings-char-row__lines">{ch.lines} lines</span>
                <button
                  className="btn btn--icon btn--danger"
                  onClick={() => deleteChar(ch.id)}
                  title="Delete character"
                >
                  <I.Cross size={14} />
                </button>
              </div>
            ))}
          </div>
          <button className="btn btn--sm" onClick={addChar}>
            + Add Character
          </button>
        </section>
      </div>
    </div>
  );
};

export default SettingsPage;
