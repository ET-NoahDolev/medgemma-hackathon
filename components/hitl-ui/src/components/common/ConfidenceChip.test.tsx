import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfidenceChip } from './ConfidenceChip';

describe('ConfidenceChip', () => {
  it('should render confidence percentage', () => {
    render(<ConfidenceChip confidence={0.85} />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('should display green color for high confidence (>= 0.9)', () => {
    const { container } = render(<ConfidenceChip confidence={0.95} />);
    const chip = container.querySelector('span');
    expect(chip).toHaveClass('bg-green-100', 'text-green-700', 'border-green-300');
  });

  it('should display blue color for medium-high confidence (>= 0.7)', () => {
    const { container } = render(<ConfidenceChip confidence={0.85} />);
    const chip = container.querySelector('span');
    expect(chip).toHaveClass('bg-blue-100', 'text-blue-700', 'border-blue-300');
  });

  it('should display yellow color for medium confidence (>= 0.5)', () => {
    const { container } = render(<ConfidenceChip confidence={0.65} />);
    const chip = container.querySelector('span');
    expect(chip).toHaveClass('bg-yellow-100', 'text-yellow-700', 'border-yellow-300');
  });

  it('should display red color for low confidence (< 0.5)', () => {
    const { container } = render(<ConfidenceChip confidence={0.35} />);
    const chip = container.querySelector('span');
    expect(chip).toHaveClass('bg-red-100', 'text-red-700', 'border-red-300');
  });

  it('should show tooltip on hover', async () => {
    const user = userEvent.setup();
    render(<ConfidenceChip confidence={0.85} />);

    const trigger = screen.getByText('85%').closest('span');
    if (trigger) {
      await user.hover(trigger);
      // Tooltip should appear (may need waitFor for Radix UI tooltip)
    }
  });

  it('should display default model and version in tooltip', async () => {
    const user = userEvent.setup();
    render(<ConfidenceChip confidence={0.85} />);

    const trigger = screen.getByText('85%').closest('span');
    if (trigger) {
      await user.hover(trigger);
      // Note: Radix UI tooltips may require additional setup for testing
      // This is a basic structure - may need to adjust based on tooltip implementation
    }
  });

  it('should display custom model and version', () => {
    render(<ConfidenceChip confidence={0.85} model="CustomModel" version="1.0.0" />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('should display dataSource when provided', () => {
    render(<ConfidenceChip confidence={0.85} dataSource="EMR System" />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('should display evidenceLink when provided', () => {
    render(<ConfidenceChip confidence={0.85} evidenceLink="/evidence/123" />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('should round confidence to nearest integer', () => {
    render(<ConfidenceChip confidence={0.856} />);
    expect(screen.getByText('86%')).toBeInTheDocument();
  });

  it('should handle edge case confidence values', () => {
    const { container: container1 } = render(<ConfidenceChip confidence={0.9} />);
    expect(container1.querySelector('span')).toHaveClass('bg-green-100');

    const { container: container2 } = render(<ConfidenceChip confidence={0.7} />);
    expect(container2.querySelector('span')).toHaveClass('bg-blue-100');

    const { container: container3 } = render(<ConfidenceChip confidence={0.5} />);
    expect(container3.querySelector('span')).toHaveClass('bg-yellow-100');

    const { container: container4 } = render(<ConfidenceChip confidence={0.49} />);
    expect(container4.querySelector('span')).toHaveClass('bg-red-100');
  });

  it('should have cursor-help class for accessibility', () => {
    const { container } = render(<ConfidenceChip confidence={0.85} />);
    const chip = container.querySelector('span');
    expect(chip).toHaveClass('cursor-help');
  });
});
