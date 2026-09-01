function [data, dt] = txf_load(txfDir)
%TXF_LOAD Load a .txf capture directory into a struct of named traces.
%   [DATA, DT] = TXF_LOAD(TXFDIR) reads metadata.json and the raw
%   traceN.bin files in TXFDIR (see scripts/txf-step.py for the format)
%   and returns DATA.<trace name> = scaled double column vector, DT = the
%   traces' hscale (sample period, s). pos_cmd/pos_fbk/pos_rx are unwrapped
%   from the firmware's [-pi, pi) wrap.

meta = jsondecode(fileread(fullfile(txfDir, 'metadata.json')));

typeMap = containers.Map( ...
    {'f32', 'i32', 'u32', 'i16', 'u16', 'i8', 'u8'}, ...
    {'single', 'int32', 'uint32', 'int16', 'uint16', 'int8', 'uint8'});

data = struct();
dt = [];
traces = meta.traces;
for i = 1:numel(traces)
    tr = traces(i);
    fid = fopen(fullfile(txfDir, tr.file), 'rb');
    raw = fread(fid, Inf, ['*' typeMap(tr.dtype)]);
    fclose(fid);
    vscale = 1.0;
    if isfield(tr, 'vscale'), vscale = tr.vscale; end
    voffset = 0.0;
    if isfield(tr, 'voffset'), voffset = tr.voffset; end
    data.(tr.name) = double(raw) * vscale + voffset;
    if isfield(tr, 'hscale'), dt = tr.hscale; end
end

posKeys = {'pos_cmd', 'pos_fbk', 'pos_rx'};
for i = 1:numel(posKeys)
    k = posKeys{i};
    if isfield(data, k) && numel(data.(k)) > 1
        data.(k) = unwrap_2pi(data.(k));
    end
end
end

function out = unwrap_2pi(x)
period = 2 * pi;
out = x;
off = 0.0;
for i = 2:numel(x)
    d = x(i) - x(i - 1);
    if d > period / 2
        off = off - period;
    elseif d < -period / 2
        off = off + period;
    end
    out(i) = x(i) + off;
end
end
