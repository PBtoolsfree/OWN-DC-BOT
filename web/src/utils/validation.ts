/**
 * Form validation utilities
 */

export function validateYouTubeInput(input: string): { valid: boolean; error?: string } {
  const trimmed = input.trim();
  if (!trimmed) {
    return { valid: false, error: 'YouTube handle or channel URL is required.' };
  }

  // Accepts @handle, channel URL, or UCxxxx channel ID
  const isHandle = /^@[\w.-]+$/.test(trimmed);
  const isChannelId = /^UC[\w-]{22}$/.test(trimmed);
  const isUrl = /^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\/.+/i.test(trimmed);

  if (isHandle || isChannelId || isUrl) {
    return { valid: true };
  }

  return {
    valid: false,
    error: 'Enter a valid @handle, channel ID (UC...), or YouTube URL.',
  };
}

export function validatePasswordStrength(password: string): { valid: boolean; error?: string } {
  if (password.length < 8) {
    return { valid: false, error: 'Password must be at least 8 characters long.' };
  }
  return { valid: true };
}
