import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SegmentedControl } from './segmented-control';

describe('SegmentedControl', () => {
  const defaultOptions = [
    { value: 'option1', label: 'Option 1' },
    { value: 'option2', label: 'Option 2' },
    { value: 'option3', label: 'Option 3' },
  ];

  it('should render all options', () => {
    render(<SegmentedControl value="option1" onValueChange={vi.fn()} options={defaultOptions} />);

    expect(screen.getByRole('button', { name: 'Option 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Option 2' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Option 3' })).toBeInTheDocument();
  });

  it('should highlight the active option', () => {
    render(<SegmentedControl value="option2" onValueChange={vi.fn()} options={defaultOptions} />);

    const activeButton = screen.getByRole('button', { name: 'Option 2' });
    const inactiveButton = screen.getByRole('button', { name: 'Option 1' });

    expect(activeButton).toHaveClass('bg-white');
    expect(inactiveButton).not.toHaveClass('bg-white');
  });

  it('should call onValueChange when option is clicked', async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(
      <SegmentedControl value="option1" onValueChange={handleChange} options={defaultOptions} />
    );

    const option2 = screen.getByRole('button', { name: 'Option 2' });
    await user.click(option2);

    expect(handleChange).toHaveBeenCalledWith('option2');
  });

  it('should apply custom active color when provided', () => {
    const customColor = '#FF5733';
    render(
      <SegmentedControl
        value="option1"
        onValueChange={vi.fn()}
        options={defaultOptions}
        activeColor={customColor}
      />
    );

    const activeButton = screen.getByRole('button', { name: 'Option 1' });
    expect(activeButton).toHaveStyle({ borderColor: customColor });
  });

  it('should render options with badges', () => {
    const optionsWithBadges = [
      { value: 'option1', label: 'Option 1', badge: <span data-testid="badge-1">5</span> },
      { value: 'option2', label: 'Option 2' },
    ];

    render(
      <SegmentedControl value="option1" onValueChange={vi.fn()} options={optionsWithBadges} />
    );

    expect(screen.getByTestId('badge-1')).toBeInTheDocument();
  });

  it('should accept custom className', () => {
    render(
      <SegmentedControl
        value="option1"
        onValueChange={vi.fn()}
        options={defaultOptions}
        className="custom-class"
      />
    );

    const container = screen.getByRole('button', { name: 'Option 1' }).parentElement;
    expect(container).toHaveClass('custom-class');
  });

  it('should handle rapid value changes', async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <SegmentedControl value="option1" onValueChange={handleChange} options={defaultOptions} />
    );

    await user.click(screen.getByRole('button', { name: 'Option 2' }));
    rerender(
      <SegmentedControl value="option2" onValueChange={handleChange} options={defaultOptions} />
    );

    await user.click(screen.getByRole('button', { name: 'Option 3' }));

    expect(handleChange).toHaveBeenCalledTimes(2);
    expect(handleChange).toHaveBeenLastCalledWith('option3');
  });

  it('should maintain accessibility attributes', () => {
    render(<SegmentedControl value="option1" onValueChange={vi.fn()} options={defaultOptions} />);

    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      expect(button).toHaveAttribute('type', 'button');
    });
  });
});
