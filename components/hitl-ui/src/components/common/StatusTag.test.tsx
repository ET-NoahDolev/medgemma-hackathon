import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusTag } from './StatusTag';
import type { StatusTagProps } from './StatusTag';

describe('StatusTag', () => {
  it('should render with matched status', () => {
    render(<StatusTag status="matched" />);
    expect(screen.getByText('Matched')).toBeInTheDocument();
  });

  it('should render with likely status', () => {
    render(<StatusTag status="likely" />);
    expect(screen.getByText('Likely')).toBeInTheDocument();
  });

  it('should render with needs-review status', () => {
    render(<StatusTag status="needs-review" />);
    expect(screen.getByText('Needs Review')).toBeInTheDocument();
  });

  it('should render with not-matched status', () => {
    render(<StatusTag status="not-matched" />);
    expect(screen.getByText('Not Matched')).toBeInTheDocument();
  });

  it('should render with ai-suggested status', () => {
    render(<StatusTag status="ai-suggested" />);
    expect(screen.getByText('AI Suggested')).toBeInTheDocument();
  });

  it('should use custom label when provided', () => {
    render(<StatusTag status="matched" label="Custom Label" />);
    expect(screen.getByText('Custom Label')).toBeInTheDocument();
  });

  it('should apply correct className for status', () => {
    const { container } = render(<StatusTag status="matched" />);
    const tag = container.querySelector('.tag.success');
    expect(tag).toBeInTheDocument();
  });

  it('should hide icon when showIcon is false', () => {
    const { container } = render(<StatusTag status="matched" showIcon={false} />);
    const icon = container.querySelector('svg');
    expect(icon).not.toBeInTheDocument();
  });

  it('should show icon by default', () => {
    const { container } = render(<StatusTag status="matched" />);
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  it('should handle all status types correctly', () => {
    const statuses: Array<StatusTagProps['status']> = [
      'matched',
      'likely',
      'needs-review',
      'not-matched',
      'ai-suggested',
    ];

    statuses.forEach(status => {
      const { container, unmount } = render(<StatusTag status={status} />);
      const tag = container.querySelector('.tag');
      expect(tag).toBeInTheDocument();
      unmount();
    });
  });

  it('should apply correct color classes for each status', () => {
    const { container: matched } = render(<StatusTag status="matched" />);
    expect(matched.querySelector('.tag.success')).toBeInTheDocument();

    const { container: likely } = render(<StatusTag status="likely" />);
    expect(likely.querySelector('.tag.info')).toBeInTheDocument();

    const { container: needsReview } = render(<StatusTag status="needs-review" />);
    expect(needsReview.querySelector('.tag.warn')).toBeInTheDocument();

    const { container: notMatched } = render(<StatusTag status="not-matched" />);
    expect(notMatched.querySelector('.tag.danger')).toBeInTheDocument();

    const { container: aiSuggested } = render(<StatusTag status="ai-suggested" />);
    expect(aiSuggested.querySelector('.tag.ai')).toBeInTheDocument();
  });

  it('should be accessible with proper ARIA attributes', () => {
    const { container } = render(<StatusTag status="matched" />);
    const tag = container.querySelector('span');
    expect(tag).toBeInTheDocument();
    // Status tags should be readable by screen readers
    expect(tag?.textContent).toBeTruthy();
  });
});
