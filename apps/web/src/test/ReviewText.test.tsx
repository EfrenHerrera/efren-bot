import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ReviewText, CodeBlock } from '@/ReviewText';

afterEach(() => vi.unstubAllGlobals());

it('separa párrafos, marcaje inline y bloques de código sin interpretar HTML', () => {
  const text = ['Revisar **el contrato** y `get_banners()`.', '', '```python',
    'if loan:', '    return "ready"', '```', '', '- Falta evidencia', '- No ejecutar', '',
    '<img src="https://example.test/pixel" onerror="alert(1)">'].join('\n');
  const { container } = render(<ReviewText text={text} />);
  expect(container.querySelector('strong')).toHaveTextContent('el contrato');
  expect(container.querySelector('p code')).toHaveTextContent('get_banners()');
  expect(container.querySelector('pre code')).toHaveTextContent('if loan:');
  expect(screen.getByText('Python')).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(2);
  expect(container.querySelector('img, script, iframe')).toBeNull();
});

it('marca las líneas de diff y copia el fragmento sin agregar marcaje ni números', async () => {
  const writeText = vi.fn(() => Promise.resolve());
  vi.stubGlobal('navigator', { clipboard: { writeText } });
  const text = '@@ -1 +1 @@\n-old_call()\n+new_call()';
  const { container } = render(<CodeBlock text={text} language="diff" label="core/example.py" />);
  expect(container.querySelector('[data-change="removed"]')).toHaveTextContent('-old_call()');
  expect(container.querySelector('[data-change="added"]')).toHaveTextContent('+new_call()');
  fireEvent.click(screen.getByRole('button', { name: 'Copiar código' }));
  expect(writeText).toHaveBeenCalledWith(text);
  expect(await screen.findByRole('button', { name: 'Copiado' })).toBeInTheDocument();
});
