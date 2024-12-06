{ pkgs }: {
  deps = [
    pkgs.lsof
    pkgs.unixtools.netstat
    pkgs.sqlite
    pkgs.imagemagick6
    pkgs.postgresql
  ];
}
