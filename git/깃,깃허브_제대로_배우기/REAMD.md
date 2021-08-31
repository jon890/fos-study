# Git, Github 제대로 배우기 (기본 마스터편, 실무에서 꿀리지 말자)

- https://www.youtube.com/watch?v=Z9dvM7qgN9s
- Terimnal, SourceTree, GitKraken 사용해보기

- Terimal : Mac => iTemr2, Windows => cmder (깃이 기본적으로 포함)
- git --version : 깃이 설치되어있는지 확인

## 처음 해야할 것

- git config --list : 깃의 모든 설정 확인
- git config --global -e : 터미널에서 에디터 모드로 설정을 연다
- code . : vscode가 열린다
- git config --global core.editor "code --wait" : 파일을 저장하고 종료하면 터미널이 활성화 됨
- git config --global user.name "BiFoS" : 글로벌 유저 네임 설정
- git config --global user.name "jon89071@gmail.com"

- git config user.email : 설정한 이메일 확인

- 캐리지 리턴 속성을 수정
- git config --global core.autocrlf true : 윈도우는 \r\n
- git config --global core.autocrlf input : Mac은 \n

## Git 공부 포인트

- 터미널에서 먼저 공부해보기
- git 다음에는 명령어가 나온다
- git commit, git add, git config

- 명령어 다음에는 옵션이 나온다
- git add -option

### Git 초기화, 삭제하기

- git init : 깃 저장소로 초기화
- master branch가 생성됨

- rm -rf .git : 깃 폴더를 삭제하고 깃 프로젝트가 아니게 됨

- git status : 상태 확인
- git config --global alias.st status : git status를 git st로만으로도 사용할 수 있게 별칭을 설정함
- git config(명령어) --h : 깃 명령어에 대한 옵션 확인

## Git 중요 컨셉 (Workflow)

- Local
- working directory (untracked/tracked)
- staging area
- .git directory

- Remote

- 커밋을 통해서 stating area에서 .git directory에 저장됨
- checkout을 통해서 언제든지 원하는 버전으로 돌아갈 수 있다
- Local의 git push를 이용해서 Remote에 저장할 수 있다
- git pull을 이용해서 Remote의 소스를 Local로 받아올 수 있다

- 각각의 커밋에는 고유한 해쉬코드가 있다
- id, message, author, date/time등의 정보도 함께 있다

## git add

- git status : 상태 확인 가능
- On branch master
- No commits yet
- Untracked files

- git add를 통해서 commit할 준비가 된 상태가 된다
- working directory => staging area

- staging area에 있는 파일을 변경시 modified로 상태가 출력된다

- git --rm --cached : staing area => untracked files

- git add . : 모든 파일들을 포함해서 staging area에 추가 된다

## git ignore

- tracking 하고 싶지 않은 파일은
- .gitignore 파일에 추가한다

## git status

- 작업하고 있는 내용들을 확인
- git status -h : usage를 알 수 있음
- git status -s : short version (A : staging area에 추가) (?? : untracked files) (AM : staging area에 추가되었지만 Modified)

## git diff

- git diff
- @@ -1 +1, 2 @@ : 1번째 줄부터 2번쨰 줄까지 내용이 추가되었다
- git diff staged : staged된 내용과 비교한다

- git diff를 다른 도구를 이용해서 확인하는 법
- git config --global -e
- diff tool => vscode
- difftool vscode => cmd = code --waiit --dif $LOCAL $REMOTE
- git difftool

## git commit

- git add.
- git commit -m "first commit" : 파일을 추가하고 first commit 메시지를 이용해서 커밋

- git commit -am "second commit" : 모든 파일을 second commit 메시지를 이용해서 커밋

## 커밋 팁

- 커다란 코끼리를 커밋에 넣지는 말자
- 그렇다고 의미없이 commit 1, commit 2.. 등으로 하진말자

- Initialize project
- Add LoginService Module
- Add UserRepository Module...
- Add Welcome page
- Add About page
- Add light theme
- 현재형 => 동사

- Fix crashing on login module
- 관심사는 꼭 하나만!
