# Future work

## Supported files

- [ ] Test more Bio-Logic files and compare the results with EC-Lab text exports.
- [ ] Test Neware NDA/NDAX with real files. These readers are still experimental;
  CSV exports are the main supported Neware workflow for now.
- [ ] Support more Neware CSV export layouts, using Total Time for elapsed time.

## Speed and memory

- [ ] Test larger files to see how much RAM and disk space conversion needs,
  and where processing is slow.
- [ ] Check whether converting two files at once is faster without using too
  much RAM. Keep sequential processing until the benefit is measured.

## Maintenance

- [ ] Validate macOS and ARM before claiming tested support.
- [ ] Recheck dependency upgrades against supported Python versions, minimum
  requirements, licensed fixtures and exact distribution artifacts.
- [ ] Add a regression for every real parsing/recognition issue.
- [ ] Keep examples runnable and notebook outputs cleared before committing.
- [ ] Review English documentation, third-party notices and limitations each release.

Cycle, capacity and energy analysis and plotting remain outside library scope.
