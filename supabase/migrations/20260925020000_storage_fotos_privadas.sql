-- Fotos do RDO: bucket privado, uma pasta por empresa.
-- Caminho dos arquivos: <empresa_id>/rdo/<rdo_id>/<arquivo>
-- O app exibe as fotos com links assinados temporários (1h).

BEGIN;

UPDATE storage.buckets SET public = false WHERE id = 'rdo-fotos';

DROP POLICY IF EXISTS rdo_fotos_leitura  ON storage.objects;
DROP POLICY IF EXISTS rdo_fotos_envio    ON storage.objects;
DROP POLICY IF EXISTS rdo_fotos_exclusao ON storage.objects;

CREATE POLICY rdo_fotos_leitura ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'rdo-fotos'
         AND (storage.foldername(name))[1] = (SELECT public.user_empresa_id())::text);

CREATE POLICY rdo_fotos_envio ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'rdo-fotos'
              AND (storage.foldername(name))[1] = (SELECT public.user_empresa_id())::text);

CREATE POLICY rdo_fotos_exclusao ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'rdo-fotos'
         AND (storage.foldername(name))[1] = (SELECT public.user_empresa_id())::text);

COMMIT;
