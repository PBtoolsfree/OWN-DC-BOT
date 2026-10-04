import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QuickSetupModal } from '../components/QuickSetupModal';
import { CustomStyleEditorModal } from '../components/CustomStyleEditorModal';
import { moderationApi } from '../api/moderation';

vi.mock('../api/moderation', () => ({
  moderationApi: {
    getQuickSetupPreview: vi.fn(),
    applyQuickSetup: vi.fn(),
    createCustomStyle: vi.fn(),
    updateCustomStyle: vi.fn(),
    deleteCustomStyle: vi.fn(),
    duplicateCustomStyle: vi.fn(),
    previewCustomStyle: vi.fn(),
  },
}));

describe('QuickSetupModal & Custom Styles Frontend Suite', () => {
  const mockQuickStyles = {
    light: {
      id: 'light',
      name: 'Light',
      description: 'Friendly community moderation.',
      decay_days: 14,
      is_builtin: true,
      actions: [
        '1st violation: Warning + DM',
        '2nd violation: Warning + DM',
        '3rd violation: Timeout 10m + DM',
        '4th violation: Timeout 1h + DM',
        '5th violation: Kick + DM',
      ],
    },
    balanced: {
      id: 'balanced',
      name: 'Balanced',
      description: 'Recommended protection for normal gaming/community servers.',
      decay_days: 30,
      is_builtin: true,
      actions: [
        '1st violation: Warning + DM',
        '2nd violation: Warning + DM',
        '3rd violation: Timeout 10m + DM',
        '4th violation: Timeout 1h + DM',
        '5th violation: Kick + DM',
        '10th violation: Ban + DM',
      ],
    },
    strict: {
      id: 'strict',
      name: 'Strict',
      description: 'Strong moderation for high-spam/high-risk communities.',
      decay_days: 60,
      is_builtin: true,
      actions: [
        '1st violation: Warning + DM',
        '2nd violation: Timeout 10m + DM',
        '3rd violation: Timeout 1h + DM',
        '4th violation: Kick + DM',
        '5th violation: Ban + DM',
      ],
    },
  };

  const mockCustomStyles = [
    {
      id: 1,
      name: 'My Custom Clan Rules',
      description: 'Custom style for gaming tournaments',
      decay_days: 7,
      allow_warning_expiration: true,
      warning_mode: 'count',
      is_builtin: false,
      actions: ['1st violation: Warning + DM', '2nd violation: Timeout 10m + DM', '3rd violation: Ban'],
      ladder: [
        { threshold: 1, action: 'warn', duration: 0, send_dm: true },
        { threshold: 2, action: 'timeout', duration: 600, send_dm: true },
        { threshold: 3, action: 'ban', duration: 0, send_dm: false },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(moderationApi.getQuickSetupPreview).mockResolvedValue({
      styles: mockQuickStyles,
      custom: mockCustomStyles,
      active_style: 'balanced',
    });
  });

  it('1 & 2 & 3 & 4. renders Quick Setup modal and allows selecting Light, Balanced, Strict', async () => {
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    render(
      <QuickSetupModal
        isOpen={true}
        onClose={onClose}
        onSuccess={onSuccess}
      />
    );

    // Modal title
    expect(screen.getByText(/Choose Moderation Style/i)).toBeInTheDocument();

    // Built-in presets available
    await waitFor(() => {
      expect(screen.getByText('Light')).toBeInTheDocument();
      expect(screen.getAllByText('Balanced').length).toBeGreaterThan(0);
      expect(screen.getByText('Strict')).toBeInTheDocument();
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });

    // Check explanation under presets (Task 18)
    expect(screen.getByText(/More forgiving. Good for friendly communities./i)).toBeInTheDocument();
    expect(screen.getByText(/Recommended balance between protection and user experience./i)).toBeInTheDocument();
    expect(screen.getByText(/Faster escalation for spam and repeated violations./i)).toBeInTheDocument();

    // Select Light tab
    fireEvent.click(screen.getByRole('button', { name: /light/i }));
    await waitFor(() => {
      expect(screen.getByText(/Friendly community moderation./i)).toBeInTheDocument();
      expect(screen.getByText(/Decay:/i)).toBeInTheDocument();
      expect(screen.getByText(/14 days/i)).toBeInTheDocument();
    });

    // Select Strict tab
    fireEvent.click(screen.getByRole('button', { name: /strict/i }));
    await waitFor(() => {
      expect(screen.getByText(/Strong moderation for high-spam\/high-risk communities./i)).toBeInTheDocument();
      expect(screen.getByText(/60 days/i)).toBeInTheDocument();
    });
  });

  it('5 & 10. allows selecting Custom tab and shows list of custom styles', async () => {
    render(
      <QuickSetupModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });

    // Switch to Custom tab
    fireEvent.click(screen.getByRole('button', { name: /custom/i }));

    await waitFor(() => {
      expect(screen.getByText('My Custom Clan Rules')).toBeInTheDocument();
      expect(screen.getByText('Custom style for gaming tournaments')).toBeInTheDocument();
      expect(screen.getByText(/Create Custom Style/i)).toBeInTheDocument();
    });
  });

  it('11 & 17. opens confirmation modal and applies preset successfully', async () => {
    vi.mocked(moderationApi.applyQuickSetup).mockResolvedValue({
      success: true,
      style: 'balanced',
      warning_decay_days: 30,
      ladder_steps_updated: 6,
      message: 'Successfully applied balanced moderation style',
    });

    const onSuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <QuickSetupModal
        isOpen={true}
        onClose={onClose}
        onSuccess={onSuccess}
      />
    );

    const applyBtn = await screen.findByRole('button', { name: /apply moderation style/i });
    await waitFor(() => {
      expect(applyBtn).not.toBeDisabled();
    });

    // Click Apply button
    fireEvent.click(applyBtn);

    // Confirmation modal should appear (Task 17)
    await waitFor(() => {
      expect(screen.getByText('Apply Balanced Moderation?')).toBeInTheDocument();
      expect(screen.getAllByText(/30 days/i).length).toBeGreaterThan(0);
    });

    // Confirm Apply
    const confirmBtn = screen.getByRole('button', { name: /^apply style$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(moderationApi.applyQuickSetup).toHaveBeenCalledWith('balanced');
      expect(onSuccess).toHaveBeenCalledWith('Successfully applied balanced moderation style');
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('12. handles apply failure safely and displays backend safe error', async () => {
    vi.mocked(moderationApi.applyQuickSetup).mockRejectedValue({
      response: {
        data: {
          detail: 'Database lock timeout. Unable to apply moderation style.',
        },
      },
    });

    render(
      <QuickSetupModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    const applyBtn = await screen.findByRole('button', { name: /apply moderation style/i });
    await waitFor(() => {
      expect(applyBtn).not.toBeDisabled();
    });

    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(screen.getByText('Apply Balanced Moderation?')).toBeInTheDocument();
    });

    const confirmBtn = screen.getByRole('button', { name: /^apply style$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByText('Database lock timeout. Unable to apply moderation style.')).toBeInTheDocument();
    });
  });

  describe('CustomStyleEditorModal Component', () => {
    it('6, 7, 8, 14. validates custom style inputs, handles adding/removing steps', async () => {
      const onSave = vi.fn();
      const onClose = vi.fn();

      render(
        <CustomStyleEditorModal
          isOpen={true}
          onClose={onClose}
          onSave={onSave}
        />
      );

      expect(screen.getByText('Create Custom Moderation Style')).toBeInTheDocument();

      // Test validation: empty name
      const saveDraftBtn = screen.getByRole('button', { name: /^save style$/i });
      fireEvent.click(saveDraftBtn);

      await waitFor(() => {
        expect(screen.getByText('Style name is required.')).toBeInTheDocument();
      });

      // Enter style name
      const nameInput = screen.getByPlaceholderText(/e\.g\. My Gaming Server/i);
      fireEvent.change(nameInput, { target: { value: 'My Tournament Rules' } });

      // Default ladder has 5 steps
      expect(screen.getByText(/Step 5:/i)).toBeInTheDocument();

      // Add a step (Task 7)
      const addStepBtn = screen.getByRole('button', { name: /add step/i });
      fireEvent.click(addStepBtn);

      // Verify 6th step appeared
      expect(screen.getByText(/Step 6:/i)).toBeInTheDocument();

      // Trigger duplicate threshold validation
      const thresholdInputs = screen.getAllByRole('spinbutton');
      fireEvent.change(thresholdInputs[1], { target: { value: '2' } });
      fireEvent.change(thresholdInputs[2], { target: { value: '2' } });

      fireEvent.click(saveDraftBtn);

      await waitFor(() => {
        expect(screen.getByText(/duplicate escalation threshold/i)).toBeInTheDocument();
      });

      // Delete step (Task 8)
      const deleteButtons = screen.getAllByTitle(/delete step/i);
      expect(deleteButtons.length).toBeGreaterThan(0);
      fireEvent.click(deleteButtons[deleteButtons.length - 1]);

      // Verify step 6 is gone
      expect(screen.queryByText(/Step 6:/i)).not.toBeInTheDocument();
    });

    it('9 & 10. allows editing an existing custom style with preloaded data', async () => {
      const existingStyle = mockCustomStyles[0];
      const onSave = vi.fn();

      render(
        <CustomStyleEditorModal
          isOpen={true}
          initialStyle={existingStyle}
          onClose={vi.fn()}
          onSave={onSave}
        />
      );

      expect(screen.getByText('Edit Custom Moderation Style')).toBeInTheDocument();
      expect(screen.getByDisplayValue('My Custom Clan Rules')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Custom style for gaming tournaments')).toBeInTheDocument();

      // Save valid edits
      const saveBtn = screen.getByRole('button', { name: /^save style$/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'My Custom Clan Rules',
            warning_decay_days: 7,
          }),
          false
        );
      });
    });
  });
});
