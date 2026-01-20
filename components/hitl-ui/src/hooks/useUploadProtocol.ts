import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadProtocolPdf } from '@/lib/api';

export function useUploadProtocol() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { file: File; autoExtract?: boolean }) =>
      uploadProtocolPdf(args.file, args.autoExtract ?? true),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['protocols'] });
    },
  });
}

