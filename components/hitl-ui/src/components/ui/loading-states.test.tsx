import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  PatientCardSkeleton,
  PatientListSkeleton,
  DashboardCardSkeleton,
  TableSkeleton,
  ProtocolCardSkeleton,
  ProtocolListSkeleton,
  ScreenLoadingFallback,
  LoadingSpinner,
} from './loading-states';

describe('LoadingStates', () => {
  describe('PatientCardSkeleton', () => {
    it('should render patient card skeleton', () => {
      const { container } = render(<PatientCardSkeleton />);
      // Check for skeleton elements
      const skeletonContainer = container.querySelector('.flex.items-center');
      expect(skeletonContainer).toBeInTheDocument();
    });
  });

  describe('PatientListSkeleton', () => {
    it('should render default count of skeletons', () => {
      const { container } = render(<PatientListSkeleton />);
      const skeletons = container.querySelectorAll('.space-y-3 > *');
      expect(skeletons.length).toBe(5); // Default count
    });

    it('should render custom count of skeletons', () => {
      const { container } = render(<PatientListSkeleton count={3} />);
      const skeletons = container.querySelectorAll('.space-y-3 > *');
      expect(skeletons.length).toBe(3);
    });
  });

  describe('DashboardCardSkeleton', () => {
    it('should render dashboard card skeleton', () => {
      const { container } = render(<DashboardCardSkeleton />);
      const cardContainer = container.querySelector('.bg-white');
      expect(cardContainer).toBeInTheDocument();
    });
  });

  describe('TableSkeleton', () => {
    it('should render table skeleton with default rows and columns', () => {
      render(<TableSkeleton />);
      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();
    });

    it('should render table skeleton with custom rows and columns', () => {
      render(<TableSkeleton rows={10} columns={6} />);
      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();

      // Check for header cells
      const headers = table.querySelectorAll('thead th');
      expect(headers.length).toBe(6);

      // Check for body rows
      const rows = table.querySelectorAll('tbody tr');
      expect(rows.length).toBe(10);
    });
  });

  describe('ProtocolCardSkeleton', () => {
    it('should render protocol card skeleton', () => {
      const { container } = render(<ProtocolCardSkeleton />);
      const skeletonContainer = container.querySelector('.space-y-2');
      expect(skeletonContainer).toBeInTheDocument();
    });
  });

  describe('ProtocolListSkeleton', () => {
    it('should render default count of protocol skeletons', () => {
      const { container } = render(<ProtocolListSkeleton />);
      const skeletons = container.querySelectorAll('.grid > *');
      expect(skeletons.length).toBe(3); // Default count
    });

    it('should render custom count of protocol skeletons', () => {
      const { container } = render(<ProtocolListSkeleton count={6} />);
      const skeletons = container.querySelectorAll('.grid > *');
      expect(skeletons.length).toBe(6);
    });
  });

  describe('ScreenLoadingFallback', () => {
    it('should render screen loading fallback', () => {
      const { container } = render(<ScreenLoadingFallback />);
      const fallbackContainer = container.querySelector('.flex.items-center');
      expect(fallbackContainer).toBeInTheDocument();
    });

    it('should have minimum height', () => {
      const { container } = render(<ScreenLoadingFallback />);
      const element = container.querySelector('.min-h-\\[400px\\]');
      expect(element).toBeInTheDocument();
    });
  });

  describe('LoadingSpinner', () => {
    it('should render loading spinner with default size', () => {
      render(<LoadingSpinner />);
      const spinner = screen.getByLabelText('Loading');
      expect(spinner).toBeInTheDocument();
      expect(spinner).toHaveClass('h-8', 'w-8'); // md size
    });

    it('should render small spinner', () => {
      render(<LoadingSpinner size="sm" />);
      const spinner = screen.getByLabelText('Loading');
      expect(spinner).toHaveClass('h-4', 'w-4');
    });

    it('should render large spinner', () => {
      render(<LoadingSpinner size="lg" />);
      const spinner = screen.getByLabelText('Loading');
      expect(spinner).toHaveClass('h-12', 'w-12');
    });

    it('should accept custom className', () => {
      render(<LoadingSpinner className="custom-spinner" />);
      const spinner = screen.getByLabelText('Loading');
      expect(spinner).toHaveClass('custom-spinner');
    });

    it('should have animation class', () => {
      render(<LoadingSpinner />);
      const spinner = screen.getByLabelText('Loading');
      expect(spinner).toHaveClass('animate-spin');
    });
  });
});
