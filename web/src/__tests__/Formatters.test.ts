import { describe, it, expect } from 'vitest';
import { formatUptime, formatDate, formatRelativeTime } from '../utils/formatters';
import { validateYouTubeInput, validatePasswordStrength } from '../utils/validation';

describe('Formatters Utility', () => {
  it('formats uptime correctly', () => {
    expect(formatUptime(0)).toBe('0m');
    expect(formatUptime(65)).toBe('1m');
    expect(formatUptime(3600)).toBe('1h 0m');
    expect(formatUptime(3665)).toBe('1h 1m');
    expect(formatUptime(86400 + 3600)).toBe('1d 1h 0m');
  });

  it('formats dates consistently', () => {
    const dateStr = '2026-10-03T11:00:00Z';
    const formatted = formatDate(dateStr);
    expect(formatted).toBeTruthy();
    expect(formatted).not.toBe('Never');

    expect(formatDate(null)).toBe('Never');
    expect(formatDate(undefined)).toBe('Never');
  });

  it('formats relative time accurately', () => {
    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000).toISOString();
    expect(formatRelativeTime(fiveMinutesAgo)).toContain('m ago');
    expect(formatRelativeTime(null)).toBe('Never');
  });
});

describe('Validation Utility', () => {
  it('validates YouTube inputs correctly', () => {
    expect(validateYouTubeInput('@PBHero').valid).toBe(true);
    expect(validateYouTubeInput('https://youtube.com/@PBHero').valid).toBe(true);
    expect(validateYouTubeInput('https://www.youtube.com/channel/UC1234567890123456789012').valid).toBe(true);
    expect(validateYouTubeInput('UC1234567890123456789012').valid).toBe(true);

    expect(validateYouTubeInput('').valid).toBe(false);
    expect(validateYouTubeInput('invalid url').valid).toBe(false);
  });

  it('validates password strength rules', () => {
    const weak = validatePasswordStrength('short');
    expect(weak.valid).toBe(false);
    expect(weak.error).toBeTruthy();

    const strong = validatePasswordStrength('AdminPassword123!');
    expect(strong.valid).toBe(true);
    expect(strong.error).toBeUndefined();
  });
});
