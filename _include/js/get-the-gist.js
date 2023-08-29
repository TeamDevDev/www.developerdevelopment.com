<script type="module">
  // import the rough notation module
  import { annotate, annotationGroup } from 'https://unpkg.com/rough-notation?module';
  // define a highlight that will be a multiple-line underline that appears for all annotated text
  const config = { type: 'underline', multiline: true, iterations: 1, strokeWidth: 3, animationDuration: 200, color: '#EF6C00', padding: 2 };
  // extract all of the elements that are designated as special
  // and thus subject to receiving the rough notation underline
  const nl = document.querySelectorAll('.gist');
  var al = []
  // create annotation objects for each of the elements
  // that are subject to rough notation underlining; these
  // are the elements that will allow the notations to either
  // appear or disappear depending on the click of the toggle
  for (let i = 0; i < nl.length; i++) {
    var newA = annotate(nl[i], config);
    al.push(newA)
  }
  // Get the checkbox element
  var toggleButtonCheckbox = document.getElementById('toggle-button-checkbox');
  // define the function that toggles the rough notation underlining
  function toggleRoughNotation() {
    if (toggleButtonCheckbox.checked) {
      // the button was checked so the script
      // should show the rough notation underlining
      for (let i = 0; i < al.length; i++) {
        var newA = al[i];
        newA.hide();
        newA.show();
      }
    } else {
      // the button was unchecked so the script
      // should hide the rough notation underlining
      for (let i = 0; i < al.length; i++) {
        var newA = al[i];
        newA.hide();
      }
    }
  }
  // Add event listener to the checkbox
  // as long as it was detected in the document
  if (toggleButtonCheckbox != null) {
    toggleButtonCheckbox.addEventListener('change', toggleRoughNotation);
  }
</script>
