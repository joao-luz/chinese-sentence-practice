// Settings page: picking a model in the OpenRouter list switches to it right away.
const modelForm = document.getElementById('model-form');
modelForm?.querySelectorAll('input[name="model"]').forEach(radio => {
    radio.addEventListener('change', () => modelForm.submit());
});
