-- ~/.config/nvim/init.lua
-- Simple Neovim configuration

-- ============================================================================
-- Basic Settings
-- ============================================================================
vim.opt.number = true              -- Show line numbers
vim.opt.relativenumber = true      -- Relative line numbers
vim.opt.mouse = 'a'                -- Enable mouse support
vim.opt.ignorecase = true          -- Case insensitive search
vim.opt.smartcase = true           -- Case sensitive if uppercase in search
vim.opt.wrap = false               -- Don't wrap lines
vim.opt.tabstop = 4                -- Tab width
vim.opt.shiftwidth = 4             -- Indent width
vim.opt.expandtab = true           -- Use spaces instead of tabs
vim.opt.termguicolors = true       -- True color support
vim.opt.signcolumn = 'yes'         -- Always show sign column
vim.opt.splitright = true          -- Vertical splits to the right
vim.opt.splitbelow = true          -- Horizontal splits below
vim.opt.clipboard = 'unnamedplus'  -- Use system clipboard
vim.opt.scrolloff = 8              -- Keep 8 lines above/below cursor
vim.opt.undofile = true            -- Persistent undo

-- Set leader key to space
vim.g.mapleader = ' '

-- ============================================================================
-- Key Mappings
-- ============================================================================
local keymap = vim.keymap.set

-- Better window navigation
keymap('n', '<C-h>', '<C-w>h')
keymap('n', '<C-j>', '<C-w>j')
keymap('n', '<C-k>', '<C-w>k')
keymap('n', '<C-l>', '<C-w>l')

-- Better indenting
keymap('v', '<', '<gv')
keymap('v', '>', '>gv')

-- Move text up and down
keymap('v', 'J', ":m '>+1<CR>gv=gv")
keymap('v', 'K', ":m '<-2<CR>gv=gv")

-- Keep cursor centered when scrolling
keymap('n', '<C-d>', '<C-d>zz')
keymap('n', '<C-u>', '<C-u>zz')

-- Clear search highlighting
keymap('n', '<Esc>', ':noh<CR>')

-- File explorer
keymap('n', '<leader>e', ':Explore<CR>')

-- Save and quit
keymap('n', '<leader>w', ':w<CR>')
keymap('n', '<leader>q', ':q<CR>')

-- ============================================================================
-- Autocommands
-- ============================================================================
-- Highlight on yank
vim.api.nvim_create_autocmd('TextYankPost', {
  callback = function()
    vim.highlight.on_yank({ timeout = 200 })
  end,
})

-- Remove trailing whitespace on save
vim.api.nvim_create_autocmd('BufWritePre', {
  pattern = '*',
  command = [[%s/\s\+$//e]],
})

-- ============================================================================
-- Plugin Manager Setup (lazy.nvim)
-- ============================================================================
local lazypath = vim.fn.stdpath('data') .. '/lazy/lazy.nvim'
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    'git', 'clone', '--filter=blob:none',
    'https://github.com/folke/lazy.nvim.git',
    '--branch=stable', lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- ============================================================================
-- Plugins
-- ============================================================================
require('lazy').setup({
  -- Color scheme
  {
    'catppuccin/nvim',
    name = 'catppuccin',
    priority = 1000,
    config = function()
      vim.cmd.colorscheme 'catppuccin-mocha'
    end,
  },

  -- Fuzzy finder
  {
    'nvim-telescope/telescope.nvim',
    dependencies = { 'nvim-lua/plenary.nvim' },
    keys = {
      { '<leader>ff', '<cmd>Telescope find_files<cr>', desc = 'Find files' },
      { '<leader>fg', '<cmd>Telescope live_grep<cr>', desc = 'Live grep' },
      { '<leader>fb', '<cmd>Telescope buffers<cr>', desc = 'Buffers' },
    },
  },

  -- Syntax highlighting
  {
    'nvim-treesitter/nvim-treesitter',
    build = ':TSUpdate',
    config = function()
      require('nvim-treesitter.configs').setup({
        ensure_installed = { 'lua', 'vim', 'python', 'javascript', 'typescript', 'bash', 'fish' },
        highlight = { enable = true },
        indent = { enable = true },
      })
    end,
  },

  -- Git signs
  { 'lewis6991/gitsigns.nvim', config = true },

  -- Auto pairs
  { 'windwp/nvim-autopairs', event = 'InsertEnter', config = true },

  -- Comments
  { 'numToStr/Comment.nvim', config = true },

  -- Status line
  {
    'nvim-lualine/lualine.nvim',
    dependencies = { 'nvim-tree/nvim-web-devicons' },
    opts = { options = { theme = 'catppuccin' } },
  },
})

