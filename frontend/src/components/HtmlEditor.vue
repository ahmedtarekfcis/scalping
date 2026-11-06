<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  List,
  ListOrdered,
  Heading2,
  Heading3,
  Palette,
  Highlighter,
  Code,
  Eraser,
  Undo2,
  Redo2,
  AlignRight,
  AlignLeft,
  Languages,
} from 'lucide-vue-next';

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: 'اكتب مراجعة الصفقة، حالتك النفسية، والدروس المستفادة هنا...',
  },
  minHeight: {
    type: String,
    default: '130px',
  },
  dir: {
    type: String,
    default: 'rtl',
  },
});

const emit = defineEmits(['update:modelValue']);

const editorRef = ref(null);
const isSourceMode = ref(false);
const sourceCode = ref('');
const currentDir = ref(props.dir || 'rtl');
const showColorPicker = ref(false);
const showHighlightPicker = ref(false);

const TEXT_COLORS = [
  { label: 'Default', value: '#f8fafc' },
  { label: 'Green', value: '#10b981' },
  { label: 'Red', value: '#f43f5e' },
  { label: 'Amber', value: '#f59e0b' },
  { label: 'Sky', value: '#0ea5e9' },
  { label: 'Purple', value: '#a855f7' },
];

const HIGHLIGHT_COLORS = [
  { label: 'None', value: 'transparent' },
  { label: 'Green Tint', value: 'rgba(16, 185, 129, 0.28)' },
  { label: 'Red Tint', value: 'rgba(244, 63, 94, 0.28)' },
  { label: 'Yellow Tint', value: 'rgba(245, 158, 11, 0.28)' },
  { label: 'Blue Tint', value: 'rgba(14, 165, 233, 0.28)' },
];

const closePickers = (e) => {
  if (!e?.target?.closest || (!e.target.closest('.color-dropdown') && !e.target.closest('.tb-btn'))) {
    showColorPicker.value = false;
    showHighlightPicker.value = false;
  }
};

// Initialize and sync content
onMounted(() => {
  if (editorRef.value) {
    editorRef.value.innerHTML = props.modelValue || '';
  }
  sourceCode.value = props.modelValue || '';
  document.addEventListener('click', closePickers);
});

onUnmounted(() => {
  document.removeEventListener('click', closePickers);
});

// External prop changes (e.g., editing a different trade)
watch(
  () => props.modelValue,
  (newVal) => {
    if (editorRef.value && editorRef.value.innerHTML !== newVal) {
      editorRef.value.innerHTML = newVal || '';
    }
    if (sourceCode.value !== newVal) {
      sourceCode.value = newVal || '';
    }
  }
);

watch(
  () => props.dir,
  (newDir) => {
    if (newDir) {
      currentDir.value = newDir;
    }
  }
);

const onInput = () => {
  if (!editorRef.value) return;
  const html = editorRef.value.innerHTML;
  sourceCode.value = html;
  emit('update:modelValue', html);
};

const onSourceInput = () => {
  emit('update:modelValue', sourceCode.value);
  if (editorRef.value) {
    editorRef.value.innerHTML = sourceCode.value;
  }
};

const execCmd = (cmd, val = null) => {
  if (isSourceMode.value) return;
  if (editorRef.value) {
    editorRef.value.focus();
  }
  document.execCommand(cmd, false, val);
  onInput();
};

const setFormatBlock = (tag) => {
  execCmd('formatBlock', tag);
};

const setTextColor = (color) => {
  execCmd('foreColor', color);
  showColorPicker.value = false;
};

const setHighlightColor = (color) => {
  execCmd('hiliteColor', color);
  showHighlightPicker.value = false;
};

const toggleDir = () => {
  currentDir.value = currentDir.value === 'rtl' ? 'ltr' : 'rtl';
};

const toggleSourceMode = () => {
  isSourceMode.value = !isSourceMode.value;
  if (!isSourceMode.value) {
    nextTick(() => {
      if (editorRef.value) {
        editorRef.value.innerHTML = sourceCode.value;
        editorRef.value.focus();
      }
    });
  }
};
</script>

<template>
  <div class="html-editor-wrapper">
    <!-- Toolbar -->
    <div class="html-editor-toolbar">
      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn"
          title="Bold (Ctrl+B)"
          @mousedown.prevent="execCmd('bold')"
        >
          <Bold :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Italic (Ctrl+I)"
          @mousedown.prevent="execCmd('italic')"
        >
          <Italic :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Underline (Ctrl+U)"
          @mousedown.prevent="execCmd('underline')"
        >
          <Underline :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Strikethrough"
          @mousedown.prevent="execCmd('strikeThrough')"
        >
          <Strikethrough :size="14" />
        </button>
      </div>

      <div class="tb-divider"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn"
          title="Heading 2"
          @mousedown.prevent="setFormatBlock('<h2>')"
        >
          <Heading2 :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Heading 3"
          @mousedown.prevent="setFormatBlock('<h3>')"
        >
          <Heading3 :size="14" />
        </button>
      </div>

      <div class="tb-divider"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn"
          title="Bullet List"
          @mousedown.prevent="execCmd('insertUnorderedList')"
        >
          <List :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Numbered List"
          @mousedown.prevent="execCmd('insertOrderedList')"
        >
          <ListOrdered :size="14" />
        </button>
      </div>

      <div class="tb-divider"></div>

      <!-- Alignment & Direction -->
      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn dir-toggle"
          :class="{ active: currentDir === 'rtl' }"
          :title="currentDir === 'rtl' ? 'Direction: Arabic RTL (يمين لليسار)' : 'Direction: LTR (Left-to-Right)'"
          @click="toggleDir"
        >
          <Languages :size="14" />
          <span class="text-xs uppercase font-bold">{{ currentDir }}</span>
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Align Right (محاذاة لليمين)"
          @mousedown.prevent="execCmd('justifyRight')"
        >
          <AlignRight :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Align Left (محاذاة لليسار)"
          @mousedown.prevent="execCmd('justifyLeft')"
        >
          <AlignLeft :size="14" />
        </button>
      </div>

      <div class="tb-divider"></div>

      <!-- Colors -->
      <div class="toolbar-group relative">
        <button
          type="button"
          class="tb-btn"
          title="Text Color"
          @click.stop="showColorPicker = !showColorPicker; showHighlightPicker = false"
        >
          <Palette :size="14" />
        </button>
        <div v-if="showColorPicker" class="color-dropdown glass-card">
          <div class="color-title">Text Color</div>
          <div class="color-swatches">
            <button
              v-for="c in TEXT_COLORS"
              :key="c.value"
              type="button"
              class="color-dot"
              :style="{ backgroundColor: c.value }"
              :title="c.label"
              @mousedown.prevent="setTextColor(c.value)"
            ></button>
          </div>
        </div>
      </div>

      <!-- Highlights -->
      <div class="toolbar-group relative">
        <button
          type="button"
          class="tb-btn"
          title="Highlight Background"
          @click.stop="showHighlightPicker = !showHighlightPicker; showColorPicker = false"
        >
          <Highlighter :size="14" />
        </button>
        <div v-if="showHighlightPicker" class="color-dropdown glass-card">
          <div class="color-title">Highlight Background</div>
          <div class="color-swatches">
            <button
              v-for="c in HIGHLIGHT_COLORS"
              :key="c.value"
              type="button"
              class="color-dot"
              :style="{ backgroundColor: c.value, border: c.value === 'transparent' ? '1px dashed #64748b' : 'none' }"
              :title="c.label"
              @mousedown.prevent="setHighlightColor(c.value)"
            ></button>
          </div>
        </div>
      </div>

      <div class="tb-divider"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn"
          title="Clear Formatting"
          @mousedown.prevent="execCmd('removeFormat')"
        >
          <Eraser :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Undo"
          @mousedown.prevent="execCmd('undo')"
        >
          <Undo2 :size="14" />
        </button>
        <button
          type="button"
          class="tb-btn"
          title="Redo"
          @mousedown.prevent="execCmd('redo')"
        >
          <Redo2 :size="14" />
        </button>
      </div>

      <div class="tb-spacer"></div>

      <!-- View HTML Source toggle -->
      <div class="toolbar-group">
        <button
          type="button"
          class="tb-btn code-btn"
          :class="{ active: isSourceMode }"
          title="Toggle HTML Source"
          @click="toggleSourceMode"
        >
          <Code :size="14" />
          <span class="text-xs">{{ isSourceMode ? 'Visual' : 'HTML' }}</span>
        </button>
      </div>
    </div>

    <!-- WYSIWYG Contenteditable Area -->
    <div
      v-show="!isSourceMode"
      ref="editorRef"
      contenteditable="true"
      class="html-editor-content"
      :class="{ 'is-rtl': currentDir === 'rtl' }"
      :dir="currentDir"
      :style="{ minHeight: minHeight, direction: currentDir, textAlign: currentDir === 'rtl' ? 'right' : 'left' }"
      :data-placeholder="placeholder"
      @input="onInput"
    ></div>

    <!-- Raw HTML Code Editor Mode -->
    <textarea
      v-show="isSourceMode"
      v-model="sourceCode"
      class="html-editor-code"
      :dir="currentDir"
      :style="{ minHeight: minHeight, direction: currentDir, textAlign: currentDir === 'rtl' ? 'right' : 'left' }"
      placeholder="Type or paste HTML code here..."
      @input="onSourceInput"
    ></textarea>
  </div>
</template>

<style scoped>
.html-editor-wrapper {
  display: flex;
  flex-direction: column;
  background: rgba(10, 14, 23, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  overflow: visible;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  position: relative;
}

.html-editor-wrapper:focus-within {
  border-color: #38bdf8;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
}

.html-editor-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(15, 23, 42, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px 8px 0 0;
  user-select: none;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 2px;
}

.tb-divider {
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.12);
  margin: 0 4px;
}

.tb-spacer {
  flex: 1;
}

.tb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 0;
}

.tb-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f8fafc;
}

.tb-btn.dir-toggle {
  width: auto;
  padding: 0 7px;
  gap: 4px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.tb-btn.dir-toggle.active {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.35);
  color: #34d399;
}

.tb-btn.code-btn {
  width: auto;
  padding: 0 8px;
  font-weight: 600;
}

.tb-btn.active {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

/* Dropdown color picker */
.color-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 8px;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  min-width: 130px;
}

.color-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.color-swatches {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.color-dot:hover {
  transform: scale(1.15);
  border-color: #fff;
}

/* Contenteditable Editor */
.html-editor-content {
  padding: 12px 14px;
  outline: none;
  color: #e2e8f0;
  font-size: 0.94rem;
  line-height: 1.6;
  border-radius: 0 0 8px 8px;
  overflow-y: auto;
}

.html-editor-content:empty::before {
  content: attr(data-placeholder);
  color: #64748b;
  pointer-events: none;
  font-style: italic;
}

/* RTL Specific formatting */
.html-editor-content.is-rtl {
  direction: rtl;
  text-align: right;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.html-editor-content.is-rtl:empty::before {
  float: right;
  direction: rtl;
  text-align: right;
  width: 100%;
}

.html-editor-content :deep(.bidi-num),
.html-editor-content .bidi-num {
  direction: ltr !important;
  unicode-bidi: isolate !important;
  display: inline-block !important;
  text-align: left !important;
  white-space: nowrap !important;
}

.html-editor-content.is-rtl :deep(ul) {
  margin: 4px 22px 4px 0;
  padding-right: 4px;
  list-style-type: disc;
  list-style-position: outside;
  direction: rtl;
  text-align: right;
}

.html-editor-content.is-rtl :deep(ol) {
  margin: 4px 22px 4px 0;
  padding-right: 4px;
  list-style-type: decimal;
  list-style-position: outside;
  direction: rtl;
  text-align: right;
}

/* Standard HTML formatting within contenteditable */
.html-editor-content :deep(h2) {
  font-size: 1.15rem;
  font-weight: 800;
  color: #38bdf8;
  margin: 8px 0 4px 0;
}

.html-editor-content :deep(h3) {
  font-size: 1.05rem;
  font-weight: 700;
  color: #7dd3fc;
  margin: 6px 0 4px 0;
}

.html-editor-content :deep(p) {
  margin: 4px 0;
}

.html-editor-content :deep(ul) {
  margin: 4px 0 4px 20px;
  list-style-type: disc;
}

.html-editor-content :deep(ol) {
  margin: 4px 0 4px 20px;
  list-style-type: decimal;
}

.html-editor-content :deep(li) {
  margin: 2px 0;
}

.html-editor-content :deep(strong),
.html-editor-content :deep(b) {
  font-weight: 700;
  color: #ffffff;
}

.html-editor-content :deep(em),
.html-editor-content :deep(i) {
  font-style: italic;
}

.html-editor-content :deep(u) {
  text-decoration: underline;
}

.html-editor-content :deep(strike),
.html-editor-content :deep(s) {
  text-decoration: line-through;
  opacity: 0.75;
}

/* Code Mode */
.html-editor-code {
  width: 100%;
  padding: 12px 14px;
  background: #020617;
  color: #38bdf8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  border: none;
  outline: none;
  resize: vertical;
  border-radius: 0 0 8px 8px;
}
</style>