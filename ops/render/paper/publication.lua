-- Publication-only layout; the Markdown source and historical archive stay intact.
function Table(t)
  local n = #t.colspecs
  if n > 8 then
    local total = n + 1.5
    for i = 1,n do t.colspecs[i][2] = (i == 1 and 2.5 or 1) / total end
    return {pandoc.RawBlock('latex', '\\begin{landscape}\\scriptsize'), t,
            pandoc.RawBlock('latex', '\\end{landscape}')}
  end
  local weights = nil
  local header = ''
  for _, row in ipairs(t.head.rows) do
    for _, cell in ipairs(row.cells) do
      header = header .. pandoc.utils.stringify(cell.contents) .. ' '
    end
  end
  if n == 8 then weights = {.19,.16,.12,.10,.11,.11,.12,.09}
  elseif n == 2 then weights = {.30,.70}
  elseif n == 3 and header:match('Family') then weights = {.14,.10,.76}
  elseif n == 3 and header:match('Finding') then weights = {.12,.38,.50}
  elseif n == 3 then weights = {.25,.30,.45}
  end
  if weights then
    for i = 1,n do t.colspecs[i][2] = weights[i] end
  end
  return t
end

function Code(c)
  if c.text:match('^[%w%./_:%-]+$') then
    return pandoc.RawInline('latex', '\\nolinkurl{' .. c.text .. '}')
  end
end

function Image(i)
  i.attributes['width'] = '100%'
  return i
end
