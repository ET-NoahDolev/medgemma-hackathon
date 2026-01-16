import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GlassButton } from './glass-button';

describe('GlassButton', () => {
  it('should render with default variant and size', () => {
    render(<GlassButton>Click me</GlassButton>);
    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('data-slot', 'glass-button');
  });

  it('should render with primary variant', () => {
    render(<GlassButton variant="primary">Primary</GlassButton>);
    const button = screen.getByRole('button', { name: 'Primary' });
    expect(button).toHaveClass('glass-button-primary');
  });

  it('should render with secondary variant', () => {
    render(<GlassButton variant="secondary">Secondary</GlassButton>);
    const button = screen.getByRole('button', { name: 'Secondary' });
    expect(button).toHaveClass('glass-button-secondary');
  });

  it('should render with outline variant', () => {
    render(<GlassButton variant="outline">Outline</GlassButton>);
    const button = screen.getByRole('button', { name: 'Outline' });
    expect(button).toHaveClass('glass-button-outline');
  });

  it('should render with ghost variant', () => {
    render(<GlassButton variant="ghost">Ghost</GlassButton>);
    const button = screen.getByRole('button', { name: 'Ghost' });
    expect(button).toHaveClass('glass-button-ghost');
  });

  it('should render with small size', () => {
    render(<GlassButton size="sm">Small</GlassButton>);
    const button = screen.getByRole('button', { name: 'Small' });
    expect(button).toHaveClass('h-8', 'px-6', 'py-1.5', 'text-xs');
  });

  it('should render with large size', () => {
    render(<GlassButton size="lg">Large</GlassButton>);
    const button = screen.getByRole('button', { name: 'Large' });
    expect(button).toHaveClass('h-12', 'px-10', 'py-3', 'text-base');
  });

  it('should render with icon size', () => {
    render(<GlassButton size="icon">Icon</GlassButton>);
    const button = screen.getByRole('button', { name: 'Icon' });
    expect(button).toHaveClass('size-10', 'p-0');
  });

  it('should handle click events', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(<GlassButton onClick={handleClick}>Click me</GlassButton>);

    const button = screen.getByRole('button', { name: 'Click me' });
    await user.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('should be disabled when disabled prop is true', () => {
    render(<GlassButton disabled>Disabled</GlassButton>);
    const button = screen.getByRole('button', { name: 'Disabled' });
    expect(button).toBeDisabled();
    expect(button).toHaveClass('disabled:pointer-events-none', 'disabled:opacity-50');
  });

  it('should not call onClick when disabled', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(
      <GlassButton disabled onClick={handleClick}>
        Disabled
      </GlassButton>
    );

    const button = screen.getByRole('button', { name: 'Disabled' });
    await user.click(button);

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('should accept custom className', () => {
    render(<GlassButton className="custom-class">Custom</GlassButton>);
    const button = screen.getByRole('button', { name: 'Custom' });
    expect(button).toHaveClass('custom-class');
  });

  it('should forward ref', () => {
    const ref = vi.fn();
    render(<GlassButton ref={ref}>Ref</GlassButton>);
    expect(ref).toHaveBeenCalled();
  });

  it('should render as child component when asChild is true', () => {
    render(
      <GlassButton asChild>
        <a href="/test">Link Button</a>
      </GlassButton>
    );
    const link = screen.getByRole('link', { name: 'Link Button' });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/test');
    expect(link).toHaveAttribute('data-slot', 'glass-button');
  });

  it('should accept standard button attributes', () => {
    render(
      <GlassButton type="submit" aria-label="Submit form">
        Submit
      </GlassButton>
    );
    const button = screen.getByRole('button', { name: 'Submit form' });
    expect(button).toHaveAttribute('type', 'submit');
  });
});
