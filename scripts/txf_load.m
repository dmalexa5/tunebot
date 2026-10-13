function [data, dt] = txf_load(txfDir)
%TXF_LOAD Load a .txf capture directory into a struct of named traces.
%   [DATA, DT] = TXF_LOAD(TXFDIR) reads metadata.json and the raw
%   traceN.bin files in TXFDIR (see scripts/txf-step.py for the format)
%   and returns DATA.<trace name> = scaled double column vector, DT = the
%   traces' hscale (sample period, s). pos_cmd/pos_fbk/pos_rx are unwrapped
%   from the firmware's [-pi, pi) wrap.
%
%   The firmware traces angles in degrees (board-drive.c @signal vscale)
%   while everything downstream works in rad, so traces whose metadata unit
%   is deg or deg/s are converted. mech_trace also names the feedback traces
%   after the encoders they come from (opos/ovel, output shaft); those are
%   aliased onto the cmd/fbk pairing, with the firmware names kept too. An
%   alias never overwrites a trace the firmware publishes under that name:
%   mech_trace now carries its own vel_fbk -- the velocity the loop actually
%   closes on, which is the rotor side through a 500 Hz biquad when
%   ctrl sets VEL_USE_MENC, and only equals ovel in the default
%   output-encoder configuration.

meta = jsondecode(fileread(fullfile(txfDir, 'metadata.json')));

% char(176) is the degree sign -- spelled this way so the file's own
% encoding can't change what it matches.
degUnits = {char(176), [char(176) '/s']};
fbkAliases = {'opos', 'pos_fbk'; 'ovel', 'vel_fbk'};

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
    scaled = double(raw) * vscale + voffset;
    if isfield(tr, 'unit') && any(strcmp(tr.unit, degUnits))
        scaled = scaled * pi / 180;
    end
    data.(tr.name) = scaled;
    if isfield(tr, 'hscale'), dt = tr.hscale; end
end

for i = 1:size(fbkAliases, 1)
    src = fbkAliases{i, 1};
    dst = fbkAliases{i, 2};
    if isfield(data, src) && ~isfield(data, dst)
        data.(dst) = data.(src);
    end
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
