import DoshaText from './DoshaText';
import { parseRecipeText, metaLabel } from '../utils/parseRecipeText';
import './RecipeMethod.css';

export default function RecipeMethod({ text }) {
  const parsed = parseRecipeText(text);
  const {
    meta,
    doshaNotes,
    tips,
    paragraphs,
    ingredients,
    steps,
    summary,
    isPlainText,
  } = parsed;

  if (isPlainText) {
    return (
      <div className="recipe-method">
        {paragraphs.map((paragraph, index) => (
          <p key={index} className="recipe-method-paragraph">
            <DoshaText text={paragraph} />
          </p>
        ))}
      </div>
    );
  }

  return (
    <div className="recipe-method">
      {meta.length > 0 && (
        <div className="recipe-method-meta">
          {meta.map((item) => (
            <span key={item.key} className="recipe-method-meta-pill">
              <span className="recipe-method-meta-label">{metaLabel(item.key)}</span>
              <span className="recipe-method-meta-value">{item.value}</span>
            </span>
          ))}
        </div>
      )}

      {paragraphs.map((paragraph, index) => (
        <p key={`intro-${index}`} className="recipe-method-paragraph recipe-method-intro">
          <DoshaText text={paragraph} />
        </p>
      ))}

      {doshaNotes.length > 0 && (
        <div className="recipe-method-dosha-notes">
          <h4 className="recipe-method-subheading">Dosha notes</h4>
          <ul className="recipe-method-dosha-list">
            {doshaNotes.map((note, index) => (
              <li key={index}>
                <DoshaText text={note} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {tips.map((tip, index) => (
        <div key={index} className="recipe-method-tip">
          <span className="recipe-method-tip-icon">💡</span>
          <p><DoshaText text={tip} /></p>
        </div>
      ))}

      {ingredients.length > 0 && (
        <section className="recipe-method-block">
          <h4 className="recipe-method-subheading">What you need</h4>
          <ul className="recipe-method-ingredients">
            {ingredients.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {steps.length > 0 && (
        <section className="recipe-method-block">
          <h4 className="recipe-method-subheading">Instructions</h4>
          <ol className="recipe-method-steps">
            {steps.map((step) => (
              <li key={step.number}>
                <DoshaText text={step.text} />
              </li>
            ))}
          </ol>
        </section>
      )}

      {summary && (
        <p className="recipe-method-paragraph recipe-method-summary">
          <DoshaText text={summary} />
        </p>
      )}
    </div>
  );
}
