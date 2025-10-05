filetype on
filetype plugin on
filetype plugin indent on

"======================================================================================================================
" Editor Settings
"======================================================================================================================
syntax enable                               " syntax highlight
set number                                  " show line numbers
set ruler
set ttyfast                                 " terminal acceleration
set cursorline                              " shows line under the cursor's line
set showmatch                               " shows matching part of bracket pairs (), [], {}
set enc=utf-8	                              " utf-8 by default
set backspace=indent,eol,start              " backspace removes all (indents, EOLs, start) What is start?
set scrolloff=10                            " let 10 lines before/after cursor during scroll
set clipboard=                              " use system clipboard

"======================================================================================================================
" Tabs and Indents
"======================================================================================================================
set tabstop=2                          " size of a hard tabstop
set shiftwidth=2                       " size of an indent
set softtabstop=2                      " a combination of spaces and tabs are used to simulate tab stops at a
                                       " width other than the (hard) tabstop
set smarttab                           " make tab insert indents instead of tabs at the beginning of a line
set expandtab                          " always uses spaces instead of tab characters
set copyindent                         " copy the same indent characters as the line before
set preserveindent                     " preserve as much of previous indent characters as possible
set autoindent                         " indent when moving to the next line while writing code

"======================================================================================================================
" Buffers settings
"======================================================================================================================
tab sball
set switchbuf=useopen
set laststatus=2
nmap <F9> :bprev<CR>
nmap <F10> :bnext<CR>
nmap <silent> <leader>q :SyntasticCheck # <CR> :bp <BAR> bd #<CR>

"======================================================================================================================
" Search settings
"======================================================================================================================
set incsearch                " incremental search
set hlsearch                 " highlight search terms
set noignorecase             " never ignore case
let hlstate=0
nnoremap <C-k> :if (hlstate == 0) \| nohlsearch \| else \| set hlsearch \| endif \| let hlstate=1-hlstate<CR>

"======================================================================================================================
" History and Backups
"======================================================================================================================
set undolevels=1000          " remember lots of undo
set nobackup                 " disable unnecessary backups
set noswapfile               " no annoying swp files

" Splits
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" open new splits below current
set splitbelow
" open new splits to the right of current
set splitright

"=====================================================
" AirLine settings
"=====================================================
let g:airline_theme='badwolf'
let g:airline#extensions#tabline#enabled=1
let g:airline#extensions#tabline#formatter='unique_tail'
let g:airline_powerline_fonts=1

"=====================================================
" NERDTree settings
"=====================================================
" Ignore files in NERDTree
let NERDTreeIgnore=['\.pyc$', '\.pyo$', '__pycache__$']
let NERDTreeWinSize=40
" Load NERDTree only if vim is run without arguments
autocmd VimEnter * if !argc() | NERDTree | endif
nmap " :NERDTreeToggle<CR>

""=====================================================
""" Python settings
""=====================================================
"
"" omnicomplete
"set completeopt-=preview                    " remove omnicompletion dropdown
"
"" python executables for different plugins
"let g:pymode_python='python'
"let g:syntastic_python_python_exec='python'
"
"" rope
"let g:pymode_rope=0
"let g:pymode_rope_completion=0
"let g:pymode_rope_complete_on_dot=0
"let g:pymode_rope_auto_project=0
"let g:pymode_rope_enable_autoimport=0
"let g:pymode_rope_autoimport_generate=0
"let g:pymode_rope_guess_project=0
"
"" documentation
"let g:pymode_doc=0
"let g:pymode_doc_key='K'
"
"" lints
"let g:pymode_lint=0
"
"" virtualenv
"let g:pymode_virtualenv=1
"
"" breakpoints
"let g:pymode_breakpoint=1
"let g:pymode_breakpoint_key='<leader>b'
"
"" syntax highlight
"let g:pymode_syntax=1
"let g:pymode_syntax_slow_sync=1
"let g:pymode_syntax_all=1
"let g:pymode_syntax_print_as_function=g:pymode_syntax_all
"let g:pymode_syntax_highlight_async_await=g:pymode_syntax_all
"let g:pymode_syntax_highlight_equal_operator=g:pymode_syntax_all
"let g:pymode_syntax_highlight_stars_operator=g:pymode_syntax_all
"let g:pymode_syntax_highlight_self=g:pymode_syntax_all
"let g:pymode_syntax_indent_errors=g:pymode_syntax_all
"let g:pymode_syntax_string_formatting=g:pymode_syntax_all
"let g:pymode_syntax_space_errors=g:pymode_syntax_all
"let g:pymode_syntax_string_format=g:pymode_syntax_all
"let g:pymode_syntax_string_templates=g:pymode_syntax_all
"let g:pymode_syntax_doctests=g:pymode_syntax_all
"let g:pymode_syntax_builtin_objs=g:pymode_syntax_all
"let g:pymode_syntax_builtin_types=g:pymode_syntax_all
"let g:pymode_syntax_highlight_exceptions=g:pymode_syntax_all
"let g:pymode_syntax_docstrings=g:pymode_syntax_all
"
"" highlight 'long' lines (>= 80 symbols) in python files
"augroup vimrc_autocmds
"    autocmd!
"    autocmd FileType python,rst,c,cpp highlight Excess ctermbg=DarkGrey guibg=Black
"    autocmd FileType python,rst,c,cpp match Excess /\%81v.*/
"    autocmd FileType python,rst,c,cpp set nowrap
"    autocmd FileType python,rst,c,cpp set colorcolumn=80
"augroup END
"
"" code folding
"let g:pymode_folding=0
"
"" pep8 indents
"let g:pymode_indent=1
"
"" code running
"let g:pymode_run=1
"let g:pymode_run_bind='<F5>'
"
"" syntastic
"let g:syntastic_always_populate_loc_list=1
"let g:syntastic_auto_loc_list=1
"let g:syntastic_enable_signs=1
"let g:syntastic_check_on_wq=0
"let g:syntastic_aggregate_errors=1
"let g:syntastic_loc_list_height=5
"let g:syntastic_error_symbol='X'
"let g:syntastic_style_error_symbol='X'
"let g:syntastic_warning_symbol='x'
"let g:syntastic_style_warning_symbol='x'
"let g:syntastic_python_checkers=['flake8', 'pydocstyle', 'python']
"
"" YouCompleteMe
"let g:ycm_global_ycm_extra_conf='~/.vim/ycm_extra_conf.py'
"let g:ycm_confirm_extra_conf=0
"nmap <leader>g :YcmCompleter GoTo<CR>
"nmap <leader>d :YcmCompleter GoToDefinition<CR>
"

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Markdown Settings
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
let g:vim_markdown_folding_level = 6

